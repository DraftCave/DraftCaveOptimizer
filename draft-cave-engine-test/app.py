"""Isolated, access-controlled engineering backend for Draft Cave Week 10.
This copies recovered GitHub engine branch e65dbe9; it is NOT the full uncommitted user ZIP
and must not be promoted as the canonical production optimizer.
"""
from __future__ import annotations
import hmac
import os
from fastapi import Request
from fastapi.responses import JSONResponse
from backend.api import app

@app.middleware("http")
async def private_api(request: Request, call_next):
    expected = os.getenv("DRAFT_CAVE_OPTIMIZER_API_KEY", "")
    supplied = request.headers.get("x-draft-cave-key", "")
    if len(expected) < 24 or not hmac.compare_digest(expected, supplied):
        return JSONResponse({"error": "Unauthorized"}, status_code=401, headers={"Cache-Control": "no-store"})
    result = await call_next(request)
    result.headers["Cache-Control"] = "private, no-store"
    return result
