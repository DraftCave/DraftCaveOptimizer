from pathlib import Path

import pytest

from models import Player
from optimizer import PLAYER_SENTIMENT_ADJUSTMENT
from ui_components import (
    SENTIMENT_ORDER,
    SENTIMENT_UI,
    resolve_player_visual,
    sentiment_display,
    sentiment_icon,
    validate_sentiment_ui_contract,
)


def _player() -> Player:
    return Player(
        dk_id=12345,
        name="Test Player",
        name_id="Test Player (12345)",
        position="WR",
        roster_positions=("WR", "FLEX"),
        salary=6000,
        team="DAL",
        opponent="PHI",
        game="DAL@PHI",
        status=None,
        projection=15.0,
        ceiling=25.0,
        ownership=10.0,
    )


def test_sentiment_ui_matches_optimizer_contract():
    validate_sentiment_ui_contract()
    assert set(SENTIMENT_UI) == set(PLAYER_SENTIMENT_ADJUSTMENT)
    assert SENTIMENT_ORDER == (
        "ADORE",
        "LOVE",
        "LIKE",
        "NEUTRAL",
        "DISLIKE",
        "HATE",
        "BAN",
    )


def test_sentiment_display_is_compact_and_human_readable():
    assert sentiment_icon("love") == "❤️"
    assert sentiment_display("neutral") == "😐 Neutral"


def test_unknown_sentiment_fails_loudly():
    with pytest.raises(ValueError):
        sentiment_icon("MAYBE")


def test_player_visual_prefers_headshot_then_team_logo(tmp_path: Path):
    player = _player()
    players_dir = tmp_path / "players"
    teams_dir = tmp_path / "teams"
    players_dir.mkdir()
    teams_dir.mkdir()

    team_logo = teams_dir / "DAL.png"
    team_logo.write_bytes(b"team")

    visual = resolve_player_visual(player, tmp_path)
    assert visual.source == "team_logo"
    assert visual.path == team_logo

    headshot = players_dir / "12345.webp"
    headshot.write_bytes(b"player")

    visual = resolve_player_visual(player, tmp_path)
    assert visual.source == "player_headshot"
    assert visual.path == headshot


def test_player_visual_uses_text_placeholder_when_assets_missing(tmp_path: Path):
    visual = resolve_player_visual(_player(), tmp_path)
    assert visual.source == "placeholder"
    assert visual.path is None
    assert "Test Player" in visual.alt_text


def test_renderable_visual_falls_back_from_corrupt_headshot(tmp_path):
    from PIL import Image
    from ui_components import player_visual_uri
    (tmp_path / "players").mkdir()
    (tmp_path / "teams").mkdir()
    (tmp_path / "players" / "12345.png").write_bytes(b"broken image")
    logo = tmp_path / "teams" / "DAL.png"
    Image.new("RGB", (40, 40), "blue").save(logo)
    assert player_visual_uri(_player(), tmp_path).startswith("data:image/png;base64,")
    logo.unlink()
    assert player_visual_uri(_player(), tmp_path).startswith("data:image/svg+xml;base64,")


def test_player_pool_identity_guard_keeps_player_name_left(monkeypatch):
    import ui_theme

    captured = {}

    def fake_data_editor(data, *args, **kwargs):
        captured.update(kwargs)
        return data

    monkeypatch.setattr(ui_theme.st, "data_editor", fake_data_editor)
    ui_theme._install_player_pool_identity_guard()

    ui_theme.st.data_editor(
        {"Player": ["Test Player"]},
        key="player_pool_editor_v5_test",
        column_order=["In Pool", "Visual", "Player", "Team", "Opp", "Pos", "Salary"],
        column_config={},
    )

    assert captured["column_order"][:5] == ["In Pool", "Player", "Pos", "Team", "Opp"]
    assert "Visual" not in captured["column_order"]
    assert "Player" in captured["column_config"]
