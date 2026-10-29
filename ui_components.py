from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import base64
from io import BytesIO

from PIL import Image

from models import Player
from optimizer import PLAYER_SENTIMENT_ADJUSTMENT


# Display-only metadata. Optimizer weights remain owned by optimizer.py.
SENTIMENT_UI = {
    "ADORE": {"icon": "😍", "label": "Adore"},
    "LOVE": {"icon": "❤️", "label": "Love"},
    "LIKE": {"icon": "🙂", "label": "Like"},
    "NEUTRAL": {"icon": "😐", "label": "Neutral"},
    "DISLIKE": {"icon": "🙁", "label": "Dislike"},
    "HATE": {"icon": "😡", "label": "Hate"},
    "BAN": {"icon": "⛔", "label": "Ban"},
}

SENTIMENT_ORDER = tuple(SENTIMENT_UI)


@dataclass(frozen=True)
class PlayerVisual:
    """Presentation-only visual identity for a player row.

    Never use these assets for roster identity. DraftKings ID remains canonical.
    """

    source: str
    path: Optional[Path]
    alt_text: str


SUPPORTED_IMAGE_SUFFIXES = (".png", ".webp", ".jpg", ".jpeg")


def sentiment_icon(sentiment: str) -> str:
    key = str(sentiment).upper()
    if key not in SENTIMENT_UI:
        raise ValueError(f"Unknown sentiment: {sentiment!r}")
    return SENTIMENT_UI[key]["icon"]


def sentiment_label(sentiment: str) -> str:
    key = str(sentiment).upper()
    if key not in SENTIMENT_UI:
        raise ValueError(f"Unknown sentiment: {sentiment!r}")
    return SENTIMENT_UI[key]["label"]


def sentiment_display(sentiment: str) -> str:
    key = str(sentiment).upper()
    return f"{sentiment_icon(key)} {sentiment_label(key)}"


def resolve_player_visual(
    player: Player,
    assets_dir: Path,
) -> PlayerVisual:
    """Resolve local visual assets with a safe deterministic fallback chain.

    Order:
      1. assets/players/<DK_ID>.<supported suffix>
      2. assets/teams/<TEAM>.<supported suffix>
      3. text placeholder (no file path)

    No network lookup and no fuzzy name matching are performed here.
    """

    player_dir = assets_dir / "players"
    team_dir = assets_dir / "teams"

    for suffix in SUPPORTED_IMAGE_SUFFIXES:
        candidate = player_dir / f"{player.dk_id}{suffix}"
        if candidate.is_file():
            return PlayerVisual(
                source="player_headshot",
                path=candidate,
                alt_text=f"{player.name} headshot",
            )

    team_key = str(player.team).strip().upper()
    for suffix in SUPPORTED_IMAGE_SUFFIXES:
        candidate = team_dir / f"{team_key}{suffix}"
        if candidate.is_file():
            return PlayerVisual(
                source="team_logo",
                path=candidate,
                alt_text=f"{team_key} team logo",
            )

    return PlayerVisual(
        source="placeholder",
        path=None,
        alt_text=f"{player.name} — {team_key} {player.position}",
    )


def validate_sentiment_ui_contract() -> None:
    """Fail loudly if UI sentiment choices drift from optimizer semantics."""

    ui_keys = set(SENTIMENT_UI)
    optimizer_keys = set(PLAYER_SENTIMENT_ADJUSTMENT)
    if ui_keys != optimizer_keys:
        missing_in_ui = sorted(optimizer_keys - ui_keys)
        missing_in_optimizer = sorted(ui_keys - optimizer_keys)
        raise RuntimeError(
            "Sentiment UI/optimizer contract drift: "
            f"missing_in_ui={missing_in_ui}, "
            f"missing_in_optimizer={missing_in_optimizer}"
        )


def player_visual_uri(player: Player, assets_dir: Path) -> str:
    """Small, verified local image; corrupt/missing assets fall through safely."""
    visual = resolve_player_visual(player, assets_dir)
    candidates = [visual.path] if visual.path else []
    team = str(player.team).strip().upper()
    # Only exact local identity keys; never allow an asset key to escape its folder.
    if team and Path(team).name == team:
        candidates += [assets_dir / "teams" / f"{team}{suffix}" for suffix in SUPPORTED_IMAGE_SUFFIXES]
    root = assets_dir.resolve()
    for path in candidates:
        if not path.resolve().is_relative_to(root):
            continue
        try:
            with Image.open(path) as source:
                source.thumbnail((28, 28))
                buffer = BytesIO()
                source.convert("RGBA").save(buffer, format="PNG")
            return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        except (OSError, ValueError):
            continue
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28"><rect width="28" height="28" rx="5" fill="#13283D"/><circle cx="14" cy="10" r="5" fill="#8296AD"/><path d="M5 26v-4a9 9 0 0 1 18 0v4" fill="#8296AD"/></svg>'
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode("ascii")
