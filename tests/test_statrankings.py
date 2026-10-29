from dataclasses import replace
import csv

import pytest

from config import OptimizerSettings
from optimizer import generate_lineups
from statrankings import COLUMNS, load_snapshot
from test_optimizer import make_player, synthetic_pool


@pytest.fixture
def player():
    return make_player(101, 'Test Player', 'WR', 'AAA', 'BBB', 5000, 15.0)


def snapshot(tmp_path, players, *overrides):
    path = tmp_path / 'snapshot.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for override in overrides:
            row = dict.fromkeys(COLUMNS, '')
            row.update(DK_ID='101', Player='Test Player', Team='AAA', Position='WR')
            row.update(override)
            writer.writerow(row)
    return load_snapshot(path, players)


def test_missing_file(tmp_path, player):
    result = load_snapshot(tmp_path / 'missing.csv', [player])
    assert result.status == 'Missing'
    assert result.evidence_by_id == result.edge_by_id == {}
    assert result.unresolved == []


def test_id_match(tmp_path, player):
    result = snapshot(tmp_path, [player], {'Player': 'Different display name', 'Edge_Score': '8'})
    assert result.edge_by_id == {101: 8.0}
    assert not result.unresolved
    settings = OptimizerSettings(statrankings_edge_by_id=result.edge_by_id)
    assert settings.statrankings_edge_by_id == {101: 8.0}


def test_fallback(tmp_path, player):
    result = snapshot(tmp_path, [player], {'DK_ID': '', 'Player': ' test   PLAYER ', 'Team': 'aaa', 'Position': 'wr'})
    assert 101 in result.evidence_by_id


@pytest.mark.parametrize('row', [
    {'Team': 'BBB'}, {'Position': 'RB'}, {'DK_ID': '999'},
    {'DK_ID': 'invalid'}, {'DK_ID': '101.0'}, {'Team': ''},
    {'DK_ID': '', 'Player': 'Unknown'}, {'Edge_Score': '8.1'},
    {'Edge_Score': '-8.1'}, {'Edge_Score': 'inf'}, {'Role_Score': '2.1'},
    {'DK_FPPG': 'oops'},
])
def test_rejected_rows(tmp_path, player, row):
    result = snapshot(tmp_path, [player], row)
    assert result.evidence_by_id == result.edge_by_id == {}
    assert len(result.unresolved) == 1


def test_conflicting_duplicates(tmp_path, player):
    result = snapshot(tmp_path, [player], {'Edge_Score': '1'}, {'Edge_Score': '2'})
    assert not result.evidence_by_id
    assert len(result.unresolved) == 2


def test_exact_duplicates(tmp_path, player):
    result = snapshot(tmp_path, [player], {'Edge_Score': '1'}, {'Edge_Score': '1'})
    assert result.edge_by_id == {101: 1.0}
    assert not result.unresolved


def test_fallback_cannot_override_duplicate_conflict(tmp_path, player):
    result = snapshot(tmp_path, [player], {'Edge_Score': '1'}, {'Edge_Score': '2'}, {'DK_ID': '', 'Edge_Score': '3'})
    assert not result.edge_by_id
    assert len(result.unresolved) == 3


def test_id_and_fallback_conflict(tmp_path, player):
    result = snapshot(tmp_path, [player], {'Edge_Score': '1'}, {'DK_ID': '', 'Edge_Score': '2'})
    assert not result.edge_by_id
    assert len(result.unresolved) == 2


@pytest.mark.parametrize('use_id', [True, False])
def test_ambiguous_slate_identity(tmp_path, player, use_id):
    other = player if use_id else replace(player, dk_id=102)
    result = snapshot(tmp_path, [player, other], {'DK_ID': '101' if use_id else ''})
    assert not result.evidence_by_id
    assert len(result.unresolved) == 1


def test_missing_numbers(tmp_path, player):
    result = snapshot(tmp_path, [player], {'Form_Score': 'NaN', 'DK_FPPG': 'NA'})
    assert result.edge_by_id == {}
    for key in ('Role_Score', 'Form_Score', 'Edge_Score', 'DK_FPPG', 'DK_FPPG_L5'):
        assert result.evidence_by_id[101][key] is None


def test_zero_is_evidence(tmp_path, player):
    result = snapshot(tmp_path, [player], {'Edge_Score': '0'})
    assert result.edge_by_id == {101: 0.0}


def test_bad_schema(tmp_path, player):
    path = tmp_path / 'bad.csv'
    path.write_text('DK_ID,Edge_Score\n101,8\n')
    result = load_snapshot(path, [player])
    assert result.status == 'Invalid file'
    assert not result.edge_by_id
    assert result.unresolved


def test_off_identical_to_baseline(tmp_path):
    players = synthetic_pool()
    p = players[0]
    result = snapshot(tmp_path, players, dict(DK_ID=str(p.dk_id), Player=p.name, Team=p.team, Position=p.position, Edge_Score='8'))
    settings = OptimizerSettings(num_lineups=4, minimum_uniques=1, randomization_pct=.15, random_seed=67)
    baseline = generate_lineups(players, settings)
    loaded = generate_lineups(players, replace(settings, statrankings_edge_by_id=result.edge_by_id))
    assert len(baseline.lineups) == len(loaded.lineups) == 4
    assert [x.player_ids for x in baseline.lineups] == [x.player_ids for x in loaded.lineups]


def test_high_changes_close_choice_without_mutation(tmp_path):
    positions = ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'RB', 'WR', 'DST']
    players = [make_player(i, f'Player {i}', pos, 'AAA', 'BBB', 4000,
                           10.0 if i == 8 else 10.1 if i == 7 else 20.0)
               for i, pos in enumerate(positions)]
    originals = [p.projection for p in players]
    result = snapshot(tmp_path, players, dict(DK_ID='8', Player='Player 8', Edge_Score='8'))
    settings = OptimizerSettings(num_lineups=1, statrankings_edge_by_id=result.edge_by_id)
    baseline = generate_lineups(players, settings)
    high = generate_lineups(players, replace(settings, statrankings_influence='HIGH'))
    assert len(baseline.lineups) == len(high.lineups) == 1
    assert 7 in baseline.lineups[0].player_ids and 8 not in baseline.lineups[0].player_ids
    assert 8 in high.lineups[0].player_ids and 7 not in high.lineups[0].player_ids
    assert [p.projection for p in players] == originals
