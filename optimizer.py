from __future__ import annotations

import math
import random
from collections import Counter, defaultdict

from ortools.sat.python import cp_model

from config import OptimizerSettings
from models import GenerationResult, Lineup, Player


ROSTER_SLOTS = (
    "QB",
    "RB1",
    "RB2",
    "WR1",
    "WR2",
    "WR3",
    "TE",
    "FLEX",
    "DST",
)


STATRANKINGS_MAX_ADJUSTMENT = {
    "OFF": 0.000,
    "LOW": 0.005,
    "MEDIUM": 0.010,
    "HIGH": 0.020,
}

PLAYER_SENTIMENT_ADJUSTMENT = {
    "ADORE": 0.100,
    "LOVE": 0.075,
    "LIKE": 0.050,
    "NEUTRAL": 0.000,
    "DISLIKE": -0.050,
    "HATE": -0.100,
    "BAN": None,
}


def statrankings_objective_adjustment(
    player: Player,
    settings: OptimizerSettings,
) -> float:
    """Return a bounded objective modifier without mutating Player.projection."""
    influence = settings.statrankings_influence.upper()
    if influence not in STATRANKINGS_MAX_ADJUSTMENT:
        raise ValueError(f"Invalid StatRankings influence level: {influence!r}")
    if influence == "OFF":
        return 0.0

    edge = settings.statrankings_edge_by_id.get(player.dk_id)
    if edge is None:
        return 0.0

    edge = max(-8.0, min(8.0, edge))
    normalized_edge = edge / 8.0
    return normalized_edge * STATRANKINGS_MAX_ADJUSTMENT[influence]


def player_sentiment_objective_adjustment(
    player: Player,
    settings: OptimizerSettings,
) -> float:
    """Return manual conviction adjustment without mutating Player.projection."""
    sentiment = settings.player_sentiment_by_id.get(
        player.dk_id,
        "NEUTRAL",
    ).upper()

    if sentiment not in PLAYER_SENTIMENT_ADJUSTMENT:
        raise ValueError(
            f"Invalid player sentiment for {player.name}: {sentiment!r}"
        )

    adjustment = PLAYER_SENTIMENT_ADJUSTMENT[sentiment]

    # BAN is handled during eligibility filtering, not as a projection penalty.
    return 0.0 if adjustment is None else float(adjustment)


def eligible_slots(player: Player) -> tuple[str, ...]:
    if player.position == "QB":
        return ("QB",)

    if player.position == "RB":
        return ("RB1", "RB2", "FLEX")

    if player.position == "WR":
        return ("WR1", "WR2", "WR3", "FLEX")

    if player.position == "TE":
        return ("TE", "FLEX")

    if player.position == "DST":
        return ("DST",)

    return tuple()


def _maximum_exposure_count(
    player: Player,
    settings: OptimizerSettings,
) -> int:
    pct = settings.player_max_exposure.get(
        player.dk_id,
        settings.position_player_caps.get(
            player.position,
            1.0,
        ),
    )

    pct = max(0.0, min(1.0, pct))

    return math.floor(
        (pct * settings.num_lineups) + 1e-9
    )


def _minimum_exposure_count(
    player: Player,
    settings: OptimizerSettings,
) -> int:
    pct = settings.player_min_exposure.get(
        player.dk_id,
        0.0,
    )

    pct = max(0.0, min(1.0, pct))

    return math.ceil(
        (pct * settings.num_lineups) - 1e-9
    )


def _make_lineup(
    players: list[Player],
    settings: OptimizerSettings,
    previous_lineups: list[Lineup],
    player_counts: Counter,
    flex_counts: Counter,
    lineup_index: int,
    rng: random.Random,
) -> Lineup | None:
    model = cp_model.CpModel()

    eligible_players: list[Player] = []

    for player in players:
        if player.dk_id in settings.exclude_players:
            continue

        sentiment = settings.player_sentiment_by_id.get(
            player.dk_id,
            "NEUTRAL",
        ).upper()
        if sentiment == "BAN":
            continue
        if sentiment not in PLAYER_SENTIMENT_ADJUSTMENT:
            raise ValueError(
                f"Invalid player sentiment for {player.name}: {sentiment!r}"
            )

        if player.projection is None:
            continue

        if (
            settings.exclude_zero_projection
            and player.projection <= 0
        ):
            continue

        if player.projection < settings.min_player_projection:
            continue

        max_count = _maximum_exposure_count(
            player,
            settings,
        )

        if player_counts[player.dk_id] >= max_count:
            continue

        eligible_players.append(player)

    slot_vars: dict[tuple[int, str], cp_model.IntVar] = {}
    player_vars: dict[int, cp_model.IntVar] = {}

    for player in eligible_players:
        pv = model.NewBoolVar(
            f"player_{player.dk_id}"
        )
        player_vars[player.dk_id] = pv

        variables = []

        for slot in eligible_slots(player):
            if slot == "FLEX":
                cap = settings.flex_position_caps.get(
                    player.position,
                    1.0,
                )

                max_flex = math.floor(
                    cap * settings.num_lineups + 1e-9
                )

                if flex_counts[player.position] >= max_flex:
                    continue

            var = model.NewBoolVar(
                f"{player.dk_id}_{slot}"
            )

            slot_vars[(player.dk_id, slot)] = var
            variables.append(var)

        if not variables:
            model.Add(pv == 0)
        else:
            model.Add(
                sum(variables) == pv
            )

    for slot in ROSTER_SLOTS:
        vars_for_slot = [
            var
            for (pid, s), var in slot_vars.items()
            if s == slot
        ]

        if not vars_for_slot:
            return None

        model.Add(sum(vars_for_slot) == 1)

    model.Add(
        sum(
            player.salary
            * player_vars[player.dk_id]
            for player in eligible_players
            if player.dk_id in player_vars
        )
        <= settings.salary_cap
    )

    if settings.minimum_salary > 0:
        model.Add(
            sum(
                player.salary
                * player_vars[player.dk_id]
                for player in eligible_players
                if player.dk_id in player_vars
            )
            >= settings.minimum_salary
        )

    for dk_id in settings.lock_players:
        if dk_id not in player_vars:
            return None

        model.Add(player_vars[dk_id] == 1)

    remaining = (
        settings.num_lineups - lineup_index
    )

    for player in eligible_players:
        required = _minimum_exposure_count(
            player,
            settings,
        )

        current = player_counts[player.dk_id]
        still_needed = max(0, required - current)

        if still_needed > remaining:
            return None

        if still_needed == remaining and still_needed > 0:
            model.Add(
                player_vars[player.dk_id] == 1
            )

    max_overlap = 9 - settings.minimum_uniques

    for old in previous_lineups:
        common_vars = [
            player_vars[pid]
            for pid in old.player_ids
            if pid in player_vars
        ]

        if common_vars:
            model.Add(
                sum(common_vars) <= max_overlap
            )

    by_team: dict[str, list[Player]] = defaultdict(list)
    by_game: dict[str, list[Player]] = defaultdict(list)

    for p in eligible_players:
        by_team[p.team].append(p)
        by_game[p.game].append(p)

    qbs = [
        p
        for p in eligible_players
        if p.position == "QB"
    ]

    for qb in qbs:
        qv = player_vars[qb.dk_id]

        stack_players = [
            player_vars[p.dk_id]
            for p in by_team[qb.team]
            if p.position in {"WR", "TE"}
            and p.dk_id in player_vars
        ]

        if stack_players:
            if settings.qb_stack_min > 0:
                model.Add(
                    sum(stack_players)
                    >= settings.qb_stack_min * qv
                )

            if settings.qb_stack_max < 8:
                model.Add(
                    sum(stack_players)
                    <= settings.qb_stack_max
                    + 8 * (1 - qv)
                )

        elif settings.qb_stack_min > 0:
            model.Add(qv == 0)

        if settings.require_bringback:
            bringbacks = [
                player_vars[p.dk_id]
                for p in by_team[qb.opponent]
                if p.position in {"RB", "WR", "TE"}
                and p.dk_id in player_vars
            ]

            if bringbacks:
                model.Add(
                    sum(bringbacks) >= qv
                )
            else:
                model.Add(qv == 0)

        if settings.max_qb_with_same_team_rb is not None:
            same_rb = [
                player_vars[p.dk_id]
                for p in by_team[qb.team]
                if p.position == "RB"
                and p.dk_id in player_vars
            ]

            if same_rb:
                model.Add(
                    sum(same_rb)
                    <= settings.max_qb_with_same_team_rb
                    + 3 * (1 - qv)
                )

        if settings.max_qb_with_same_team_dst is not None:
            same_dst = [
                player_vars[p.dk_id]
                for p in by_team[qb.team]
                if p.position == "DST"
                and p.dk_id in player_vars
            ]

            if same_dst:
                model.Add(
                    sum(same_dst)
                    <= settings.max_qb_with_same_team_dst
                    + (1 - qv)
                )

    if settings.max_offense_vs_opposing_dst is not None:
        dsts = [
            p
            for p in eligible_players
            if p.position == "DST"
        ]

        for dst in dsts:
            dv = player_vars[dst.dk_id]

            opposing_offense = [
                player_vars[p.dk_id]
                for p in by_team[dst.opponent]
                if p.position != "DST"
                and p.dk_id in player_vars
            ]

            if opposing_offense:
                model.Add(
                    sum(opposing_offense)
                    <= settings.max_offense_vs_opposing_dst
                    + 8 * (1 - dv)
                )

    if settings.require_secondary_stack:
        secondary_game_vars = []

        for game, game_players in by_game.items():
            teams = sorted(
                set(
                    p.team
                    for p in game_players
                    if p.position in {"RB", "WR", "TE"}
                )
            )

            if len(teams) != 2:
                continue

            team_a, team_b = teams

            a_players = [
                player_vars[p.dk_id]
                for p in game_players
                if p.team == team_a
                and p.position in {"RB", "WR", "TE"}
                and p.dk_id in player_vars
            ]

            b_players = [
                player_vars[p.dk_id]
                for p in game_players
                if p.team == team_b
                and p.position in {"RB", "WR", "TE"}
                and p.dk_id in player_vars
            ]

            if not a_players or not b_players:
                continue

            a_present = model.NewBoolVar(
                f"sec_{game}_{team_a}"
            )
            b_present = model.NewBoolVar(
                f"sec_{game}_{team_b}"
            )

            model.Add(
                sum(a_players) >= a_present
            )
            model.Add(
                sum(a_players)
                <= len(a_players) * a_present
            )

            model.Add(
                sum(b_players) >= b_present
            )
            model.Add(
                sum(b_players)
                <= len(b_players) * b_present
            )

            sec = model.NewBoolVar(
                f"secondary_{game}"
            )

            model.Add(sec <= a_present)
            model.Add(sec <= b_present)
            model.Add(
                sec >= a_present + b_present - 1
            )

            for qb in qbs:
                if qb.game == game:
                    model.Add(
                        sec <= 1 - player_vars[qb.dk_id]
                    )

            secondary_game_vars.append(sec)

        if not secondary_game_vars:
            return None

        model.Add(
            sum(secondary_game_vars) >= 1
        )

    ownership_available = all(
        p.ownership is not None
        for p in eligible_players
    )

    if (
        settings.ownership_min is not None
        or settings.ownership_max is not None
    ):
        if not ownership_available:
            raise ValueError(
                "Ownership constraint requested but ownership "
                "data is incomplete. Draft Cave fails closed."
            )

        ownership_scale = 1000

        ownership_expr = sum(
            int(round(p.ownership * ownership_scale))
            * player_vars[p.dk_id]
            for p in eligible_players
        )

        if settings.ownership_min is not None:
            model.Add(
                ownership_expr
                >= int(
                    round(
                        settings.ownership_min
                        * ownership_scale
                    )
                )
            )

        if settings.ownership_max is not None:
            model.Add(
                ownership_expr
                <= int(
                    round(
                        settings.ownership_max
                        * ownership_scale
                    )
                )
            )

    objective_terms = []
    objective_scale = 10_000

    for player in eligible_players:
        projection = player.projection or 0.0

        if settings.randomization_pct > 0:
            low = 1.0 - settings.randomization_pct
            high = 1.0 + settings.randomization_pct

            multiplier = rng.uniform(low, high)
            projection *= multiplier

        sr_adjustment = statrankings_objective_adjustment(player, settings)
        sentiment_adjustment = player_sentiment_objective_adjustment(
            player,
            settings,
        )
        objective_projection = (
            projection
            * (1.0 + sr_adjustment)
            * (1.0 + sentiment_adjustment)
        )

        value = (
            settings.projection_weight
            * objective_projection
        )

        if (
            settings.ceiling_weight != 0
            and player.ceiling is not None
        ):
            value += (
                settings.ceiling_weight
                * player.ceiling
            )

        objective_terms.append(
            int(round(value * objective_scale))
            * player_vars[player.dk_id]
        )

    for qb in qbs:
        qv = player_vars[qb.dk_id]

        for p in eligible_players:
            if p.dk_id == qb.dk_id:
                continue

            boost = 0.0

            if (
                p.team == qb.team
                and p.position in {"WR", "TE"}
            ):
                boost = settings.sim_same_team_pct

            elif (
                p.team == qb.opponent
                and p.position in {"RB", "WR", "TE"}
            ):
                boost = settings.sim_opponent_pct

            if boost <= 0:
                continue

            pair = model.NewBoolVar(
                f"sim_{qb.dk_id}_{p.dk_id}"
            )

            model.Add(
                pair <= qv
            )
            model.Add(
                pair <= player_vars[p.dk_id]
            )
            model.Add(
                pair
                >= qv + player_vars[p.dk_id] - 1
            )

            bonus = (
                (p.projection or 0.0)
                * boost
            )

            objective_terms.append(
                int(round(bonus * objective_scale))
                * pair
            )

    model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()

    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = settings.random_seed

    status = solver.Solve(model)

    if status not in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    ):
        return None

    lineup_slots: dict[str, Player] = {}

    player_lookup = {
        p.dk_id: p
        for p in eligible_players
    }

    for (pid, slot), var in slot_vars.items():
        if solver.Value(var):
            lineup_slots[slot] = player_lookup[pid]

    if len(lineup_slots) != 9:
        return None

    return Lineup(slots=lineup_slots)


def generate_lineups(
    players: list[Player],
    settings: OptimizerSettings,
) -> GenerationResult:
    rng = random.Random(settings.random_seed)

    lineups: list[Lineup] = []

    player_counts = Counter()
    flex_counts = Counter()

    warnings: list[str] = []

    for i in range(settings.num_lineups):
        lineup = _make_lineup(
            players=players,
            settings=settings,
            previous_lineups=lineups,
            player_counts=player_counts,
            flex_counts=flex_counts,
            lineup_index=i,
            rng=rng,
        )

        if lineup is None:
            warnings.append(
                f"Generation stopped after {len(lineups)} "
                f"lineups; remaining constraints were infeasible."
            )
            break

        lineups.append(lineup)

        for player in lineup.players:
            player_counts[player.dk_id] += 1

        flex_counts[
            lineup.flex.position
        ] += 1

    for player in players:
        required = _minimum_exposure_count(
            player,
            settings,
        )

        if required > 0:
            actual = player_counts[player.dk_id]

            if actual < required:
                warnings.append(
                    f"Minimum exposure not satisfied for "
                    f"{player.name}: {actual}/{required}."
                )

    return GenerationResult(
        lineups=lineups,
        warnings=warnings,
        diagnostics={
            "generated": len(lineups),
            "requested": settings.num_lineups,
            "player_counts": dict(player_counts),
            "flex_counts": dict(flex_counts),
        },
    )