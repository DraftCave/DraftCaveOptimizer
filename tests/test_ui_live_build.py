import base64
import json
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from ui_matchups import load_dvp, sort_pool, team_cell_uri, dvp_style
from test_optimizer import synthetic_pool


def test_sort_numeric_missing_and_deterministic_ties():
    frame = pd.DataFrame({"ID": [4, 3, 2, 1], "Own %": [None, 9.3, 14.4, 14.4]})
    assert sort_pool(frame, "Own %", True).ID.tolist() == [1, 2, 3, 4]
    assert sort_pool(frame, "Own %", False).ID.tolist() == [3, 1, 2, 4]
    assert frame.ID.tolist() == [4, 3, 2, 1]


def snapshot():
    p = synthetic_pool()[0]
    return dict(salary_sha256="current", rank_direction="1_easiest_32_hardest",
                source="Synthetic test", source_url="https://example.org/test",
                as_of="2026-10-29T12:00:00Z", verified_by="test fixture",
                rows=[dict(opponent=p.opponent, position=p.position, rank=8)])


def test_dvp_valid_partial_and_missing(tmp_path):
    path = tmp_path / "dvp.json"
    assert load_dvp(path, "current", synthetic_pool())[0] == {}
    data = snapshot()
    path.write_text(json.dumps(data))
    values, status = load_dvp(path, "current", synthetic_pool())
    assert list(values.values()) == [8]
    assert "Synthetic test" in status
    data["rows"][0]["rank"] = None
    path.write_text(json.dumps(data))
    assert list(load_dvp(path, "current", synthetic_pool())[0].values()) == [None]


@pytest.mark.parametrize("change", [
    {"salary_sha256": "old"}, {"rank_direction": "unknown"}, {"verified_by": ""},
    {"as_of": "bad date"}, {"rows": [{"opponent": "UNKNOWN", "position": "QB", "rank": 3}]},
])
def test_dvp_invalid_metadata_fails_closed(tmp_path, change):
    path = tmp_path / "dvp.json"
    path.write_text(json.dumps(snapshot() | change))
    assert load_dvp(path, "current", synthetic_pool())[0] == {}


@pytest.mark.parametrize("rank", [0, 33, True, 1.5, "8"])
def test_dvp_invalid_rank_fails_closed(tmp_path, rank):
    data = snapshot()
    data["rows"][0]["rank"] = rank
    path = tmp_path / "dvp.json"
    path.write_text(json.dumps(data))
    assert load_dvp(path, "current", synthetic_pool())[0] == {}


def test_dvp_colors_and_missing():
    assert dvp_style(None) == ""
    assert len({dvp_style(i) for i in [1, 9, 17, 25]}) == 4
    for lo, hi in [(1, 8), (9, 16), (17, 24), (25, 32)]:
        assert dvp_style(lo) == dvp_style(hi)


def test_team_cells_local_assets_and_safe_fallback(tmp_path):
    for team in ["DAL", "UNKNOWN", "../../secret"]:
        uri = team_cell_uri(team, str(tmp_path))
        with Image.open(BytesIO(base64.b64decode(uri.split(",")[1]))) as img:
            assert img.size == (84, 28)
            assert img.getbbox() is not None
    assets = Path(__file__).resolve().parents[1] / "assets"
    assert len(list((assets / "teams").glob("*.png"))) == 34
    assert team_cell_uri("DAL", str(assets)) != team_cell_uri("DAL", str(tmp_path))


def test_live_build_state_and_generation(slate_dir, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from test_v5_repair import edit_row, pool_editor
    import optimizer

    # Isolate persistence and private files; exercise the real UI with a synthetic slate.
    root = Path(__file__).resolve().parents[1]
    source = (root / "app.py").read_text(encoding="utf-8")
    source = source.replace('BASE_DIR = Path(__file__).resolve().parent', f'BASE_DIR = Path({str(slate_dir.parent)!r})')
    calls = []
    original = optimizer.generate_lineups

    def capture(players, settings):
        calls.append((players, settings))
        return original(players, settings)

    monkeypatch.setattr(optimizer, "generate_lineups", capture)
    projections = pd.read_csv(slate_dir / "projections.csv")
    projections["Ownership"] = [9.3 if i % 2 else 14.4 for i in range(len(projections))]
    projections.to_csv(slate_dir / "projections.csv", index=False)
    at = AppTest.from_string(source, default_timeout=60).run()
    assert not at.exception
    assert len([c for c in at.checkbox if c.label == "Show research columns"]) == 1
    next(n for n in at.number_input if n.label == "Candidate Lineups").set_value(3).run()
    at.radio(key="active_position").set_value("WR").run()
    at.selectbox(key="pool_sort").set_value("Proj").run()
    at.radio(key="pool_sort_direction").set_value("Low to high").run()
    assert not at.exception
    at.number_input(key="group_exposure_max_WR").set_value(80).run()
    at.checkbox(key="in_pool_all_WR").uncheck().run()
    assert at.session_state.active_position == "WR"
    assert at.session_state.pool_sort == "Proj"
    assert at.session_state.pool_sort_direction == "Low to high"
    at.checkbox(key="in_pool_all_WR").check().run()
    at.selectbox(key="pool_sort").set_value("Own %").run()
    at.radio(key="pool_sort_direction").set_value("High to low").run()
    frame = pool_editor(at).value
    assert frame["Own %"].notna().all()
    assert frame["Own %"].is_monotonic_decreasing
    pid = int(frame.iloc[0]["ID"])
    edit_row(at, 0, {"In Pool": False, "Sentiment": "😍 Adore", "Min %": 0, "Max %": 60})
    assert at.session_state.player_controls[pid]["Exclude"]
    assert at.session_state.player_controls[pid]["Sentiment"] == "ADORE"
    assert at.session_state.player_controls[pid]["Max %"] == 60
    assert pool_editor(at).value["Own %"].is_monotonic_decreasing
    at.selectbox(key="pool_sort").set_value("Proj").run()
    # Editing after a new sort must still affect the displayed player's ID.
    next_pid = int(pool_editor(at).value.iloc[0]["ID"])
    edit_row(at, 0, {"Max %": 90})
    assert at.session_state.player_controls[next_pid]["Max %"] == 90
    at.run()
    assert not at.exception
    at.button(key="generate_lineups").click().run(timeout=120)
    assert not at.exception
    assert len(calls) == 1
    assert at.session_state.active_position == "WR"
    assert at.session_state.pool_sort == "Proj"
    assert at.session_state.generated_portfolio_review_position == "WR"
    assert not hasattr(calls[0][1], "dvp")
    assert all(not hasattr(p, "dvp") for p in calls[0][0])
    before = at.session_state.generation_result
    # Adding visual DVP cannot change the solver inputs or generated lineup IDs.
    from ui_matchups import slate_digest
    data = snapshot()
    data["salary_sha256"] = slate_digest(slate_dir / "DKSalaries.csv")
    (slate_dir / "dvp.json").write_text(json.dumps(data))
    at.button(key="generate_lineups").click().run(timeout=120)
    assert not at.exception
    assert calls[0] == calls[1]
    assert [l.player_ids for l in before.lineups] == [l.player_ids for l in at.session_state.generation_result.lineups]
