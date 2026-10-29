from __future__ import annotations

from dataclasses import replace

import pytest

from config import OptimizerSettings
from models import Player
from optimizer import generate_lineups, statrankings_objective_adjustment


def make_player(
    dk_id: int,
    name: str,
    position: str,
    team: str,
    opponent: str,
    salary: int,
    projection: float,
) -> Player:
    roster_positions = {
        "QB": ("QB",),
        "RB": ("RB", "FLEX"),
        "WR": ("WR", "FLEX"),
        "TE": ("TE", "FLEX"),
        "DST": ("DST",),
    }[position]

    return Player(
        dk_id=dk_id,
        name=name,
        name_id=f"{name} ({dk_id})",
        position=position,
        roster_positions=roster_positions,
        salary=salary,
        team=team,
        opponent=opponent,
        game="@".join(sorted([team, opponent])),
        status=None,
        projection=projection,
    )


def synthetic_pool() -> list[Player]:
    players = []
    pid = 1

    games = [
        ("AAA", "BBB"),
        ("CCC", "DDD"),
        ("EEE", "FFF"),
    ]

    for team, opponent in games:
        players.append(
            make_player(
                pid,
                f"{team} QB",
                "QB",
                team,
                opponent,
                6500,
                22.0,
            )
        )
        pid += 1

        for i in range(3):
            players.append(
                make_player(
                    pid,
                    f"{team} RB{i}",
                    "RB",
                    team,
                    opponent,
                    6000 - i * 400,
                    16.0 - i,
                )
            )
            pid += 1

        for i in range(5):
            players.append(
                make_player(
                    pid,
                    f"{team} WR{i}",
                    "WR",
                    team,
                    opponent,
                    5800 - i * 300,
                    15.0 - i * 0.5,
                )
            )
            pid += 1

        for i in range(2):
            players.append(
                make_player(
                    pid,
                    f"{team} TE{i}",
                    "TE",
                    team,
                    opponent,
                    4200 - i * 300,
                    11.0 - i,
                )
            )
            pid += 1

        players.append(
            make_player(
                pid,
                f"{team} DST",
                "DST",
                team,
                opponent,
                3000,
                7.0,
            )
        )
        pid += 1

    return players


def paired_synthetic_pool() -> list[Player]:
    players = []
    pid = 1000

    games = [
        ("AAA", "BBB"),
        ("CCC", "DDD"),
        ("EEE", "FFF"),
    ]

    for team_a, team_b in games:
        for team, opponent in [
            (team_a, team_b),
            (team_b, team_a),
        ]:
            players.append(
                make_player(
                    pid,
                    f"{team} QB",
                    "QB",
                    team,
                    opponent,
                    6200,
                    21.0,
                )
            )
            pid += 1

            for i in range(2):
                players.append(
                    make_player(
                        pid,
                        f"{team} RB{i}",
                        "RB",
                        team,
                        opponent,
                        5600 - i * 400,
                        15.0 - i,
                    )
                )
                pid += 1

            for i in range(3):
                players.append(
                    make_player(
                        pid,
                        f"{team} WR{i}",
                        "WR",
                        team,
                        opponent,
                        5400 - i * 400,
                        14.0 - i * 0.5,
                    )
                )
                pid += 1

            players.append(
                make_player(
                    pid,
                    f"{team} TE0",
                    "TE",
                    team,
                    opponent,
                    4000,
                    10.0,
                )
            )
            pid += 1

            players.append(
                make_player(
                    pid,
                    f"{team} DST",
                    "DST",
                    team,
                    opponent,
                    3000,
                    7.0,
                )
            )
            pid += 1

    return players


def sim_same_team_pool() -> tuple[list[Player], int, int, int]:
    players = [
        make_player(
            2000,
            "AAA QB",
            "QB",
            "AAA",
            "BBB",
            6000,
            20.0,
        ),
        make_player(
            2001,
            "CCC RB",
            "RB",
            "CCC",
            "DDD",
            5000,
            15.0,
        ),
        make_player(
            2002,
            "DDD RB",
            "RB",
            "DDD",
            "CCC",
            5000,
            15.0,
        ),
        make_player(
            2003,
            "EEE RB FLEX",
            "RB",
            "EEE",
            "FFF",
            4000,
            12.0,
        ),
        make_player(
            2004,
            "FFF WR Fixed",
            "WR",
            "FFF",
            "EEE",
            4500,
            13.0,
        ),
        make_player(
            2005,
            "GGG WR Fixed",
            "WR",
            "GGG",
            "HHH",
            4500,
            13.0,
        ),
        make_player(
            2006,
            "AAA WR Correlated",
            "WR",
            "AAA",
            "BBB",
            4500,
            10.0,
        ),
        make_player(
            2007,
            "HHH WR Unrelated",
            "WR",
            "HHH",
            "GGG",
            4500,
            10.5,
        ),
        make_player(
            2008,
            "III TE",
            "TE",
            "III",
            "JJJ",
            3500,
            10.0,
        ),
        make_player(
            2009,
            "KKK DST",
            "DST",
            "KKK",
            "LLL",
            3000,
            7.0,
        ),
    ]

    return (
        players,
        2000,
        2006,
        2007,
    )


def sim_opponent_pool() -> tuple[list[Player], int, int, int]:
    players = [
        make_player(
            3000,
            "AAA QB",
            "QB",
            "AAA",
            "BBB",
            6000,
            20.0,
        ),
        make_player(
            3001,
            "CCC RB",
            "RB",
            "CCC",
            "DDD",
            5000,
            15.0,
        ),
        make_player(
            3002,
            "DDD RB",
            "RB",
            "DDD",
            "CCC",
            5000,
            15.0,
        ),
        make_player(
            3003,
            "EEE RB FLEX",
            "RB",
            "EEE",
            "FFF",
            4000,
            12.0,
        ),
        make_player(
            3004,
            "FFF WR Fixed",
            "WR",
            "FFF",
            "EEE",
            4500,
            13.0,
        ),
        make_player(
            3005,
            "GGG WR Fixed",
            "WR",
            "GGG",
            "HHH",
            4500,
            13.0,
        ),
        make_player(
            3006,
            "BBB WR Bringback",
            "WR",
            "BBB",
            "AAA",
            4500,
            10.0,
        ),
        make_player(
            3007,
            "HHH WR Unrelated",
            "WR",
            "HHH",
            "GGG",
            4500,
            10.5,
        ),
        make_player(
            3008,
            "III TE",
            "TE",
            "III",
            "JJJ",
            3500,
            10.0,
        ),
        make_player(
            3009,
            "KKK DST",
            "DST",
            "KKK",
            "LLL",
            3000,
            7.0,
        ),
    ]

    return (
        players,
        3000,
        3006,
        3007,
    )


def fixed_sim_locks(players: list[Player]) -> set[int]:
    candidate_ids = {
        2006,
        2007,
        3006,
        3007,
    }

    return {
        player.dk_id
        for player in players
        if player.dk_id not in candidate_ids
    }


def lineup_signatures(lineups):
    return [
        tuple(sorted(lineup.player_ids))
        for lineup in lineups
    ]


def player_exposure_count(
    lineups,
    dk_id: int,
) -> int:
    return sum(
        dk_id in lineup.player_ids
        for lineup in lineups
    )


def test_generates_legal_lineups():
    players = synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=10,
        minimum_uniques=1,
    )

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 10

    for lineup in result.lineups:
        assert len(lineup.players) == 9
        assert len(lineup.player_ids) == 9
        assert lineup.salary <= 50000

        positions = [
            p.position
            for p in lineup.players
        ]

        assert positions.count("QB") == 1
        assert positions.count("DST") == 1
        assert positions.count("RB") >= 2
        assert positions.count("WR") >= 3
        assert positions.count("TE") >= 1


def test_minimum_uniques():
    players = synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=8,
        minimum_uniques=3,
        randomization_pct=0.20,
    )

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 8

    for i, a in enumerate(result.lineups):
        for b in result.lineups[i + 1:]:
            overlap = len(
                a.player_ids & b.player_ids
            )

            assert overlap <= 6


def test_qb_stack():
    players = synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
        qb_stack_min=1,
        qb_stack_max=2,
    )

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    for lineup in result.lineups:
        qb = lineup.qb

        partners = [
            p
            for p in lineup.players
            if p.team == qb.team
            and p.position in {"WR", "TE"}
        ]

        assert 1 <= len(partners) <= 2


def test_randomization_reproducible():
    players = synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=6,
        minimum_uniques=2,
        randomization_pct=0.20,
        random_seed=123,
    )

    result_a = generate_lineups(
        players,
        settings,
    )

    result_b = generate_lineups(
        players,
        settings,
    )

    assert lineup_signatures(
        result_a.lineups
    ) == lineup_signatures(
        result_b.lineups
    )


def test_different_random_seeds_change_output():
    players = synthetic_pool()

    settings_a = OptimizerSettings(
        num_lineups=8,
        minimum_uniques=2,
        randomization_pct=0.50,
        random_seed=42,
    )

    settings_b = OptimizerSettings(
        num_lineups=8,
        minimum_uniques=2,
        randomization_pct=0.50,
        random_seed=99,
    )

    result_a = generate_lineups(
        players,
        settings_a,
    )

    result_b = generate_lineups(
        players,
        settings_b,
    )

    assert lineup_signatures(
        result_a.lineups
    ) != lineup_signatures(
        result_b.lineups
    )


def test_minimum_salary():
    players = synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
        minimum_salary=48000,
    )

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    for lineup in result.lineups:
        assert lineup.salary >= 48000
        assert lineup.salary <= 50000


def test_lock_player():
    players = synthetic_pool()

    target = players[1]

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
    )

    settings.lock_players = {
        target.dk_id
    }

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    for lineup in result.lineups:
        assert target.dk_id in lineup.player_ids


def test_exclude_player():
    players = synthetic_pool()

    target = players[1]

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
    )

    settings.exclude_players = {
        target.dk_id
    }

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    for lineup in result.lineups:
        assert target.dk_id not in lineup.player_ids


def test_player_max_exposure():
    players = synthetic_pool()

    target = players[1]

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
    )

    settings.player_max_exposure = {
        target.dk_id: 0.40
    }

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    assert player_exposure_count(
        result.lineups,
        target.dk_id,
    ) <= 2


def test_player_min_exposure():
    players = synthetic_pool()

    target = players[1]

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
    )

    settings.player_min_exposure = {
        target.dk_id: 0.60
    }

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    assert player_exposure_count(
        result.lineups,
        target.dk_id,
    ) >= 3


def test_qb_player_exposure_cap():
    players = synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
    )

    settings.position_player_caps["QB"] = 0.40

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    qb_ids = {
        p.dk_id
        for p in players
        if p.position == "QB"
    }

    for qb_id in qb_ids:
        assert player_exposure_count(
            result.lineups,
            qb_id,
        ) <= 2


def test_require_bringback():
    players = paired_synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
        qb_stack_min=1,
        qb_stack_max=2,
        require_bringback=True,
    )

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    for lineup in result.lineups:
        qb = lineup.qb

        bringbacks = [
            p
            for p in lineup.players
            if p.team == qb.opponent
            and p.position in {"RB", "WR", "TE"}
        ]

        assert len(bringbacks) >= 1


def test_require_secondary_stack():
    players = paired_synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
        require_secondary_stack=True,
    )

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    for lineup in result.lineups:
        qb = lineup.qb

        qb_game_teams = {
            qb.team,
            qb.opponent,
        }

        secondary_skill_players = [
            p
            for p in lineup.players
            if p.position in {"RB", "WR", "TE"}
            and p.team not in qb_game_teams
        ]

        found_secondary_stack = False

        for player_a in secondary_skill_players:
            for player_b in secondary_skill_players:
                if player_a.dk_id == player_b.dk_id:
                    continue

                if (
                    player_a.team == player_b.opponent
                    and player_b.team == player_a.opponent
                ):
                    found_secondary_stack = True
                    break

            if found_secondary_stack:
                break

        assert found_secondary_stack


def test_max_qb_with_same_team_rb_zero():
    players = paired_synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
        max_qb_with_same_team_rb=0,
    )

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    for lineup in result.lineups:
        qb = lineup.qb

        assert not any(
            p.team == qb.team
            and p.position == "RB"
            for p in lineup.players
        )


def test_max_qb_with_same_team_dst_zero():
    players = paired_synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
        max_qb_with_same_team_dst=0,
    )

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    for lineup in result.lineups:
        qb = lineup.qb

        assert not any(
            p.team == qb.team
            and p.position == "DST"
            for p in lineup.players
        )


def test_max_offense_vs_opposing_dst_zero():
    players = paired_synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
        max_offense_vs_opposing_dst=0,
    )

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    for lineup in result.lineups:
        dst = next(
            p
            for p in lineup.players
            if p.position == "DST"
        )

        assert not any(
            p.team == dst.opponent
            and p.position != "DST"
            for p in lineup.players
        )


def test_te_flex_cap_zero():
    players = paired_synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
    )

    settings.flex_position_caps["TE"] = 0.0

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    for lineup in result.lineups:
        assert lineup.flex.position != "TE"


def test_ownership_bounds():
    players = [
        replace(
            player,
            ownership=10.0,
        )
        for player in paired_synthetic_pool()
    ]

    settings = OptimizerSettings(
        num_lineups=5,
        minimum_uniques=1,
        ownership_min=90.0,
        ownership_max=90.0,
    )

    result = generate_lineups(
        players,
        settings,
    )

    assert len(result.lineups) == 5

    for lineup in result.lineups:
        total_ownership = sum(
            player.ownership
            for player in lineup.players
        )

        assert total_ownership == pytest.approx(
            90.0
        )


def test_ownership_fails_closed_when_missing():
    players = paired_synthetic_pool()

    settings = OptimizerSettings(
        num_lineups=1,
        minimum_uniques=1,
        ownership_max=120.0,
    )

    with pytest.raises(
        ValueError,
        match="Ownership constraint requested",
    ):
        generate_lineups(
            players,
            settings,
        )


def test_same_team_sim_boost_changes_choice():
    (
        players,
        qb_id,
        correlated_id,
        unrelated_id,
    ) = sim_same_team_pool()

    baseline_settings = OptimizerSettings(
        num_lineups=1,
        minimum_uniques=1,
        sim_same_team_pct=0.0,
    )

    baseline_settings.lock_players = fixed_sim_locks(
        players
    )

    boosted_settings = OptimizerSettings(
        num_lineups=1,
        minimum_uniques=1,
        sim_same_team_pct=0.10,
    )

    boosted_settings.lock_players = fixed_sim_locks(
        players
    )

    baseline = generate_lineups(
        players,
        baseline_settings,
    )

    boosted = generate_lineups(
        players,
        boosted_settings,
    )

    assert len(baseline.lineups) == 1
    assert len(boosted.lineups) == 1

    baseline_ids = baseline.lineups[0].player_ids
    boosted_ids = boosted.lineups[0].player_ids

    assert qb_id in baseline_ids
    assert qb_id in boosted_ids

    assert unrelated_id in baseline_ids
    assert correlated_id not in baseline_ids

    assert correlated_id in boosted_ids
    assert unrelated_id not in boosted_ids


def test_opponent_sim_boost_changes_choice():
    (
        players,
        qb_id,
        opponent_id,
        unrelated_id,
    ) = sim_opponent_pool()

    baseline_settings = OptimizerSettings(
        num_lineups=1,
        minimum_uniques=1,
        sim_opponent_pct=0.0,
    )

    baseline_settings.lock_players = fixed_sim_locks(
        players
    )

    boosted_settings = OptimizerSettings(
        num_lineups=1,
        minimum_uniques=1,
        sim_opponent_pct=0.10,
    )

    boosted_settings.lock_players = fixed_sim_locks(
        players
    )

    baseline = generate_lineups(
        players,
        baseline_settings,
    )

    boosted = generate_lineups(
        players,
        boosted_settings,
    )

    assert len(baseline.lineups) == 1
    assert len(boosted.lineups) == 1

    baseline_ids = baseline.lineups[0].player_ids
    boosted_ids = boosted.lineups[0].player_ids

    assert qb_id in baseline_ids
    assert qb_id in boosted_ids

    assert unrelated_id in baseline_ids
    assert opponent_id not in baseline_ids

    assert opponent_id in boosted_ids
    assert unrelated_id not in boosted_ids

@pytest.mark.parametrize(
    "influence, edge, expected",
    [
        ("OFF", 8.0, 0.0),
        ("HIGH", None, 0.0),
        ("LOW", 8.0, 0.005),
        ("MEDIUM", 8.0, 0.010),
        ("HIGH", 8.0, 0.020),
        ("LOW", -8.0, -0.005),
        ("MEDIUM", -8.0, -0.010),
        ("HIGH", -8.0, -0.020),
        ("MEDIUM", 4.0, 0.005),
        ("HIGH", 80.0, 0.020),
        ("HIGH", -80.0, -0.020),
        ("medium", 8.0, 0.010),
    ],
)
def test_statrankings_objective_adjustment(influence, edge, expected):
    player = make_player(9001, "Evidence WR", "WR", "AAA", "BBB", 5000, 15.0)
    settings = OptimizerSettings(
        statrankings_influence=influence,
        statrankings_edge_by_id={} if edge is None else {player.dk_id: edge},
    )

    assert statrankings_objective_adjustment(player, settings) == pytest.approx(expected)


def test_statrankings_preserves_projection():
    player = make_player(9001, "Evidence WR", "WR", "AAA", "BBB", 5000, 15.0)
    original_projection = player.projection
    settings = OptimizerSettings(
        statrankings_influence="HIGH",
        statrankings_edge_by_id={player.dk_id: 8.0},
    )

    statrankings_objective_adjustment(player, settings)

    assert player.projection == original_projection


def test_statrankings_invalid_influence_fails_closed():
    player = make_player(9001, "Evidence WR", "WR", "AAA", "BBB", 5000, 15.0)
    settings = OptimizerSettings(statrankings_influence="INVALID")

    with pytest.raises(ValueError, match="Invalid StatRankings influence level"):
        statrankings_objective_adjustment(player, settings)
