"""Authenticated, immutable-snapshot adapter. No Warehouse reads or writes."""
import csv
import hashlib
import hmac
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.api import OptimizeRequest, run_optimization
from config import raw_baseline
from data_loader import join_projections, load_dk_salaries, load_projection_table
from optimizer import ROSTER_SLOTS, is_optimizer_eligible, optimizer_ineligibility_reason

app = FastAPI(title="Draft Cave website adapter", docs_url=None, redoc_url=None, openapi_url=None)
generation_lock = Lock()


@app.middleware("http")
async def authenticate(request: Request, call_next):
    key = os.environ.get("DRAFT_CAVE_OPTIMIZER_KEY", "")
    if not key:
        return JSONResponse({"detail": "Optimizer service is not configured."}, status_code=503)
    if not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + key):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    response = await call_next(request)
    response.headers["Cache-Control"] = "private, no-store"
    return response


def load_snapshot():
    """Read each input once, verify its bytes, then solve those exact bytes."""
    location = os.environ.get("DRAFT_CAVE_OPTIMIZER_MANIFEST")
    if not location:
        raise HTTPException(503, "No approved optimizer snapshot configured.")
    try:
        path = Path(location).resolve()
        manifest_bytes = path.read_bytes()
        m = json.loads(manifest_bytes)
        phase = m["phase"]
        if phase not in {"PRE_LOCK", "TECHNICAL_REPLAY"}:
            raise ValueError("POST-LOCK data is not an optimizer input.")
        if not isinstance(m["slate"], str) or not m["slate"].strip():
            raise ValueError("A slate label is required.")
        if phase == "PRE_LOCK":
            captured = datetime.fromisoformat(m["captured_at"])
            locks = datetime.fromisoformat(m["lock_at"])
            now = datetime.now(timezone.utc)
            if captured.tzinfo is None or locks.tzinfo is None or not captured <= now < locks:
                raise ValueError("Snapshot is future-dated or locked; use an explicit technical replay.")
        blobs = {}
        for kind in ("salary", "projection"):
            blobs[kind] = (path.parent / m[kind + "_file"]).read_bytes()
            if hashlib.sha256(blobs[kind]).hexdigest() != m[kind + "_sha256"]:
                raise ValueError("Snapshot hash mismatch; refresh the approved manifest.")
        players, report = join_projections(
            load_dk_salaries(io.BytesIO(blobs["salary"])),
            load_projection_table(io.BytesIO(blobs["projection"])), source_name=m["slate"])
        snapshot = {"snapshot_id": hashlib.sha256(manifest_bytes).hexdigest(),
                    "slate": m["slate"], "phase": phase,
                    "salary_sha256": m["salary_sha256"], "projection_sha256": m["projection_sha256"]}
        return snapshot, players, report
    except (OSError, KeyError, TypeError, ValueError) as exc:
        # Never expose deployment paths or private input contents.
        raise HTTPException(422, "Snapshot invalid, changed, or locked. Review its manifest and input files.") from exc


@app.get("/snapshot")
def snapshot():
    info, players, _ = load_snapshot()
    settings = raw_baseline()
    return {**info, "player_count": len(players),
            "optimizer_eligible_count": sum(is_optimizer_eligible(p, settings) for p in players),
            "players": [{"dk_id": p.dk_id, "name": p.name, "position": p.position,
                         "team": p.team, "opponent": p.opponent, "salary": p.salary,
                         "projection": p.projection, "ownership": p.ownership, "ceiling": p.ceiling,
                         "eligibility_state": p.eligibility_state,
                         "optimizer_eligible": is_optimizer_eligible(p, settings),
                         "ineligibility_reason": optimizer_ineligibility_reason(p, settings)} for p in players]}


class GenerateRequest(BaseModel):
    model_config = {"extra": "forbid"}
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    settings: OptimizeRequest


@app.post("/generate")
def generate(request: GenerateRequest):
    if request.settings.num_lineups > 300:
        raise HTTPException(422, "Website generation is limited to 300 candidates per request.")
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(429, "Generation already running; wait before retrying.")
    try:
        info, players, report = load_snapshot()
        if request.snapshot_id != info["snapshot_id"]:
            raise HTTPException(409, "Snapshot changed. Reload before generating.")
        result = run_optimization(request.settings, players, report)
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"])
        for lineup in result["lineups"]:
            writer.writerow([lineup["players"][slot]["name_id"] for slot in ROSTER_SLOTS])
        return {**info, **result, "settings": request.settings.model_dump(mode="json"),
                "dk_csv": output.getvalue(), "candidate_only": True}
    finally:
        generation_lock.release()


@app.exception_handler(ValueError)
async def invalid_settings(request: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=422)
