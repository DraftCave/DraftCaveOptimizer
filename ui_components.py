from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
