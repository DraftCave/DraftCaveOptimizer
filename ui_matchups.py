"""Display-only matchup metadata. Never imported by the optimizer or Player model."""
from __future__ import annotations

import base64
import hashlib
import json
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def slate_digest(source):
    payload = source.read_bytes() if isinstance(source, Path) else source.getvalue()
    return hashlib.sha256(payload).hexdigest()


def load_dvp(path, salary_digest, players):
    """Require an explicitly verified, slate-bound source with documented direction.

    Rank 1 = easiest, 32 = hardest. No inference from StatRankings Matchup_Score.
    Return missing on any invalid snapshot; partial valid coverage is permitted.
    """
    if not path.exists():
        return {}, "DVP unavailable: no verified slate-specific source supplied."
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
            raise ValueError("snapshot must be an object with a rows list")
        if data.get("salary_sha256") != salary_digest:
            raise ValueError("salary-file fingerprint does not match this slate")
        if data.get("rank_direction") != "1_easiest_32_hardest":
            raise ValueError("rank direction must be 1_easiest_32_hardest")
        for field in ("source", "source_url", "as_of", "verified_by"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                raise ValueError(f"missing {field}")
        from datetime import datetime
        datetime.fromisoformat(data["as_of"].replace("Z", "+00:00"))
        allowed = {(p.opponent, p.position) for p in players}
        values = {}
        for row in data["rows"]:
            if not isinstance(row, dict):
                raise ValueError("each row must be an object")
            key = (row["opponent"], row["position"])
            if key not in allowed or key in values:
                raise ValueError(f"unresolved or duplicate opponent/position: {key}")
            rank = row["rank"]
            if rank is not None and (type(rank) is not int or not 1 <= rank <= 32):
                raise ValueError("rank must be an integer 1–32 or null")
            values[key] = rank
        return values, f"DVP: {data['source']} · as of {data['as_of']} · verified by {data['verified_by']} · {data['source_url']}"
    except (ValueError, TypeError, KeyError, OSError) as exc:
        return {}, f"DVP unavailable: {exc}"


def dvp_style(rank):
    # These are display bins, not a predictive model or optimizer intervention.
    import pandas as pd
    if pd.isna(rank):
        return ""
    background, foreground = (
        ("#164B38", "#9DF0C9") if rank <= 8 else
        ("#4B4217", "#FFF09C") if rank <= 16 else
        ("#543419", "#FFD0A0") if rank <= 24 else
        ("#54252B", "#FFB9C0")
    )
    return f"background-color: {background}; color: {foreground}; font-weight: bold"


def sort_pool(frame, column, descending):
    """Presentation order only. Stable DK-ID ties, missing values always last."""
    return frame.sort_values([column, "ID"], ascending=[not descending, True],
                             na_position="last", kind="stable").reset_index(drop=True)


@lru_cache(maxsize=128)
def team_cell_uri(team, assets_dir):
    """Logo and readable abbreviation inside one compact image cell; local only."""
    key = str(team).strip().upper()
    if not key.isascii() or not key.isalpha() or len(key) > 4:
        key = "—"
    canvas = Image.new("RGBA", (84, 28), (0, 0, 0, 0))
    for suffix in (".png", ".webp", ".jpg", ".jpeg"):
        try:
            with Image.open(Path(assets_dir) / "teams" / f"{key}{suffix}") as logo:
                logo = logo.convert("RGBA")
                logo.thumbnail((24, 24))
                canvas.alpha_composite(logo, ((26-logo.width)//2, (28-logo.height)//2))
            break
        except (OSError, ValueError):
            continue
    ImageDraw.Draw(canvas).text((29, 6), key, font=ImageFont.load_default(size=15), fill="#EAF2FA")
    buffer = BytesIO()
    canvas.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
