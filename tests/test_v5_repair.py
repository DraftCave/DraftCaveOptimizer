import json
from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from config import OptimizerSettings
from optimizer import generate_lineups, player_sentiment_objective_adjustment
from test_optimizer import make_player, synthetic_pool


@pytest.mark.parametrize('sentiment,expected', [
    ('ADORE', .10), ('LOVE', .075), ('LIKE', .05), ('NEUTRAL', 0),
    ('DISLIKE', -.05), ('HATE', -.10), ('BAN', 0), ('love', .075),
])
def test_sentiment_mapping(sentiment, expected):
    player = synthetic_pool()[0]
    before = player.projection
    settings = OptimizerSettings(player_sentiment_by_id={player.dk_id: sentiment})
    assert player_sentiment_objective_adjustment(player, settings) == expected
    assert player.projection == before


def test_sentiment_changes_choice_without_mutating_projection():
    positions = ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'RB', 'WR', 'DST']
    players = [make_player(i, f'Test {i}', pos, 'AAA', 'BBB', 4000,
                          10.0 if i == 8 else 10.1 if i == 7 else 20.0)
               for i, pos in enumerate(positions)]
    original = [p.projection for p in players]
    settings = OptimizerSettings(num_lineups=1)
    baseline = generate_lineups(players, settings)
    liked = generate_lineups(players, replace(settings, player_sentiment_by_id={8: 'LIKE'}))
    assert 7 in baseline.lineups[0].player_ids
    assert 8 not in baseline.lineups[0].player_ids
    assert 8 in liked.lineups[0].player_ids
    assert 7 not in liked.lineups[0].player_ids
    assert [p.projection for p in players] == original
    assert liked.lineups[0].projection == sum(p.projection for p in liked.lineups[0].players)


def test_ban_exclusion_and_neutral_randomization():
    players = synthetic_pool()
    original = [p.projection for p in players]
    settings = OptimizerSettings(num_lineups=4, minimum_uniques=1,
                                 randomization_pct=.2, random_seed=123)
    baseline = generate_lineups(players, settings)
    neutral = generate_lineups(players, replace(settings, player_sentiment_by_id={p.dk_id: 'NEUTRAL' for p in players}))
    assert [l.player_ids for l in baseline.lineups] == [l.player_ids for l in neutral.lineups]
    banned_id = baseline.lineups[0].qb.dk_id
    banned = generate_lineups(players, replace(settings, player_sentiment_by_id={banned_id: 'BAN'}))
    assert len(banned.lineups) == 4
    assert all(banned_id not in l.player_ids for l in banned.lineups)
    assert [p.projection for p in players] == original


@pytest.fixture
def ui(tmp_path, monkeypatch, slate_dir):
    # Run the actual app against copied inputs; never overwrite the user's saved reservoir.
    import shutil
    source = Path(__file__).resolve().parents[1]
    shutil.copy2(source / 'app.py', tmp_path / 'app.py')
    (tmp_path / 'data' / '.draft_cave_last_run.pkl').unlink(missing_ok=True)
    at = AppTest.from_file(str(tmp_path / 'app.py'), default_timeout=30).run()
    assert not at.exception
    return at


def pool_editor(at):
    return next(d for d in at.dataframe if 'In Pool' in d.value.columns)


def edit_row(at, row, changes):
    editor = pool_editor(at)
    states = at._tree.get_widget_states()
    state = states.widgets.add()
    state.id = editor.proto.id
    state.string_value = json.dumps({'edited_rows': {str(row): changes}, 'added_rows': [], 'deleted_rows': []})
    at._run(states)
    assert not at.exception


def test_pool_controls_generation_and_persistence(ui):
    at = ui
    frame = pool_editor(at).value
    assert 'Lock' not in frame and 'Exclude' not in frame
    first, second = map(int, frame['ID'].iloc[:2])
    edit_row(at, 0, {'In Pool': False})
    assert at.session_state.player_controls[first]['Exclude']
    assert not at.checkbox(key='in_pool_all_ALL').value
    at.checkbox(key='in_pool_all_ALL').check().run()
    assert not any(c['Exclude'] for c in at.session_state.player_controls.values())
    at.checkbox(key='in_pool_all_ALL').uncheck().run()
    assert all(c['Exclude'] for c in at.session_state.player_controls.values())
    at.checkbox(key='in_pool_all_ALL').check().run()
    edit_row(at, 0, {'In Pool': False})
    edit_row(at, 1, {'Sentiment': '⛔ Ban'})
    assert not pool_editor(at).value.iloc[1]['In Pool']
    at.radio(key='active_position').set_value('RB').run()
    at.number_input(key='group_exposure_min_RB').set_value(5).run()
    at.number_input(key='group_exposure_min_RB').set_value(0).run()
    assert not at.exception
    assert at.number_input(key='group_exposure_min_RB').value == 0
    assert at.session_state.player_controls[first]['Exclude']
    assert at.session_state.player_controls[second]['Sentiment'] == 'BAN'
    at.radio(key='active_position').set_value('ALL').run()
    # Limit runtime while exercising real UI -> settings -> solver -> results.
    count = next(n for n in at.number_input if 'lineup' in n.label.lower())
    count.set_value(2).run()
    next(b for b in at.button if b.label.startswith('GENERATE ')).click().run(timeout=60)
    assert not at.exception
    settings = at.session_state.generation_settings
    assert {first, second} <= settings.exclude_players
    assert settings.player_sentiment_by_id[second] == 'BAN'
    result = at.session_state.generation_result
    assert len(result.lineups) == 2
    assert all(not ({first, second} & l.player_ids) for l in result.lineups)
    at.radio(key='generated_portfolio_review_position').set_value('RB').run()
    assert not at.exception
    assert any('RB FLEX' in d.value.columns for d in at.dataframe)
    assert at.session_state.generation_result == result
    restored = AppTest.from_file(at._script_path, default_timeout=30).run()
    assert not restored.exception
    assert restored.session_state.generation_restored_from_cache
    assert [l.player_ids for l in restored.session_state.generation_result.lineups] == [l.player_ids for l in result.lineups]


def test_separate_lock_and_filtered_bulk_controls(ui):
    at = ui
    initial = pool_editor(at).value
    qb_id = int(initial.loc[initial['Pos'] == 'QB', 'ID'].iloc[0])
    at.multiselect(key='locked_players_multiselect_v5').set_value([qb_id]).run()
    assert at.session_state.player_controls[qb_id]['Lock']
    at.radio(key='active_position').set_value('RB').run()
    rb_ids = set(map(int, pool_editor(at).value['ID']))
    at.checkbox(key='in_pool_all_RB').uncheck().run()
    excluded = {pid for pid, c in at.session_state.player_controls.items() if c['Exclude']}
    assert excluded == rb_ids
    assert at.session_state.player_controls[qb_id]['Lock']
    at.checkbox(key='in_pool_all_RB').check().run()
    at.radio(key='active_position').set_value('QB').run()
    assert pool_editor(at).value['In Pool'].all()
    # Lock/BAN conflicts are shown, never silently ignored.
    row = list(map(int, pool_editor(at).value['ID'])).index(qb_id)
    edit_row(at, row, {'Sentiment': '⛔ Ban'})
    assert any('both locked and excluded' in e.value for e in at.error)
    assert not at.exception


def test_bulk_exposure_only_changes_active_position(ui):
    at = ui
    initial = pool_editor(at).value
    rb_ids = set(map(int, initial.loc[initial['Pos'] == 'RB', 'ID']))
    non_rb_ids = set(map(int, initial.loc[initial['Pos'] != 'RB', 'ID']))
    before_non_rb = {
        pid: (
            at.session_state.player_controls[pid]['Min %'],
            at.session_state.player_controls[pid]['Max %'],
        )
        for pid in non_rb_ids
    }

    at.radio(key='active_position').set_value('RB').run()
    assert set(map(int, pool_editor(at).value['ID'])) == rb_ids
    at.number_input(key='group_exposure_min_RB').set_value(10).run()
    at.number_input(key='group_exposure_max_RB').set_value(35).run()

    assert not at.exception
    for pid in rb_ids:
        assert at.session_state.player_controls[pid]['Min %'] == 10
        assert at.session_state.player_controls[pid]['Max %'] == 35
    for pid, expected in before_non_rb.items():
        controls = at.session_state.player_controls[pid]
        assert (controls['Min %'], controls['Max %']) == expected


def test_sentiment_cells_keep_identity_and_missing_metrics(ui):
    at = ui
    frame = pool_editor(at).value
    pid = int(frame.iloc[0]['ID'])
    projections = dict(zip(frame['ID'], frame['Base Proj']))
    assert frame['Own %'].isna().all()
    assert frame['Ceiling'].isna().all()
    from ui_components import sentiment_display
    for state in ('ADORE', 'LOVE', 'LIKE', 'NEUTRAL', 'DISLIKE', 'HATE', 'BAN'):
        edit_row(at, 0, {'Sentiment': sentiment_display(state)})
        assert not at.exception
        assert at.session_state.player_controls[pid]['Sentiment'] == state
        current = pool_editor(at).value
        assert dict(zip(current['ID'], current['Base Proj'])) == projections
    edit_row(at, 0, {'Sentiment': sentiment_display('NEUTRAL')})
    assert at.session_state.player_controls[pid]['Exclude']  # unbanning does not silently re-add
