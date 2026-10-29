from __future__ import annotations

import itertools
import math
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from models import Lineup


def lineup_table(
    lineups: list[Lineup],
) -> pd.DataFrame:
    rows = []

    for idx, lineup in enumerate(lineups, start=1):
        row = {
            "Lineup": idx,
            "Projection": lineup.projection,
            "Ceiling": lineup.ceiling,
            "Ownership": lineup.ownership,
            "Salary": lineup.salary,
            "SalaryLeft": 50_000 - lineup.salary,
            "QBStory": str(lineup.story_signature()),
        }

        for slot, player in lineup.slots.items():
            row[slot] = player.name

        rows.append(row)

    return pd.DataFrame(rows)


def player_exposure(
    lineups: list[Lineup],
) -> pd.DataFrame:
    counts = Counter()
    player_lookup = {}

    for lineup in lineups:
        for player in lineup.players:
            counts[player.dk_id] += 1
            player_lookup[player.dk_id] = player

    n = len(lineups)

    rows = []

    for dk_id, count in counts.items():
        p = player_lookup[dk_id]

        rows.append(
            {
                "Name": p.name,
                "Position": p.position,
                "Team": p.team,
                "Count": count,
                "Exposure": (
                    count / n
                    if n
                    else 0.0
                ),
                "Projection": p.projection,
                "Ownership": p.ownership,
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(
            ["Exposure", "Position", "Name"],
            ascending=[False, True, True],
        )
        .reset_index(drop=True)
    )


def qb_exposure(
    lineups: list[Lineup],
) -> pd.DataFrame:
    counts = Counter(
        lineup.qb.name
        for lineup in lineups
    )

    n = len(lineups)

    return pd.DataFrame(
        [
            {
                "QB": name,
                "Count": count,
                "Exposure": count / n,
            }
            for name, count in counts.most_common()
        ]
    )


def flex_distribution(
    lineups: list[Lineup],
) -> pd.DataFrame:
    counts = Counter(
        lineup.flex.position
        for lineup in lineups
    )

    n = len(lineups)

    return pd.DataFrame(
        [
            {
                "Position": pos,
                "Count": count,
                "Rate": count / n,
            }
            for pos, count in counts.items()
        ]
    )


def repeated_pairs(
    lineups: list[Lineup],
    top_n: int = 25,
) -> pd.DataFrame:
    counts = Counter()
    labels = {}

    for lineup in lineups:
        ordered = sorted(
            lineup.players,
            key=lambda p: p.dk_id,
        )

        for a, b in itertools.combinations(
            ordered,
            2,
        ):
            key = (a.dk_id, b.dk_id)

            counts[key] += 1
            labels[key] = (
                a.name,
                b.name,
            )

    n = len(lineups)

    rows = []

    for key, count in counts.most_common(top_n):
        a, b = labels[key]

        rows.append(
            {
                "PlayerA": a,
                "PlayerB": b,
                "Count": count,
                "Rate": count / n,
            }
        )

    return pd.DataFrame(rows)


def repeated_cores(
    lineups: list[Lineup],
    core_size: int = 3,
    top_n: int = 20,
) -> pd.DataFrame:
    counts = Counter()
    labels = {}

    for lineup in lineups:
        ordered = sorted(
            lineup.players,
            key=lambda p: p.dk_id,
        )

        for combo in itertools.combinations(
            ordered,
            core_size,
        ):
            key = tuple(
                p.dk_id
                for p in combo
            )

            counts[key] += 1
            labels[key] = tuple(
                p.name
                for p in combo
            )

    n = len(lineups)

    rows = []

    for key, count in counts.most_common(top_n):
        if count <= 1:
            continue

        rows.append(
            {
                "Core": " + ".join(labels[key]),
                "Count": count,
                "Rate": count / n,
            }
        )

    return pd.DataFrame(rows)


def pairwise_overlap_summary(
    lineups: list[Lineup],
) -> dict:
    overlaps = []

    for a, b in itertools.combinations(
        lineups,
        2,
    ):
        overlaps.append(
            len(
                a.player_ids
                & b.player_ids
            )
        )

    if not overlaps:
        return {
            "mean_overlap": 0.0,
            "max_overlap": 0,
            "p90_overlap": 0.0,
        }

    return {
        "mean_overlap": float(
            np.mean(overlaps)
        ),
        "max_overlap": int(
            max(overlaps)
        ),
        "p90_overlap": float(
            np.percentile(overlaps, 90)
        ),
    }


def effective_player_count(
    lineups: list[Lineup],
) -> float:
    if not lineups:
        return 0.0

    counts = Counter(
        p.dk_id
        for lineup in lineups
        for p in lineup.players
    )

    total_slots = len(lineups) * 9

    shares = [
        count / total_slots
        for count in counts.values()
    ]

    hhi = sum(
        share * share
        for share in shares
    )

    return (
        1.0 / hhi
        if hhi > 0
        else 0.0
    )


def effective_qb_count(
    lineups: list[Lineup],
) -> float:
    if not lineups:
        return 0.0

    counts = Counter(
        lineup.qb.dk_id
        for lineup in lineups
    )

    n = len(lineups)

    shares = [
        count / n
        for count in counts.values()
    ]

    hhi = sum(
        share * share
        for share in shares
    )

    return (
        1.0 / hhi
        if hhi > 0
        else 0.0
    )


def story_family_exposure(
    lineups: list[Lineup],
) -> pd.DataFrame:
    counts = Counter(
        lineup.story_signature()
        for lineup in lineups
    )

    n = len(lineups)

    rows = []

    for signature, count in counts.most_common():
        rows.append(
            {
                "Signature": str(signature),
                "Count": count,
                "Rate": count / n,
            }
        )

    return pd.DataFrame(rows)


def team_skill_risk(
    lineups: list[Lineup],
) -> pd.DataFrame:
    """
    Measures shared team-level skill-player dependence.

    This is risk-factor exposure, not a judgment that
    concentration is automatically bad.
    """
    incidence = Counter()
    multi_incidence = Counter()

    n = len(lineups)

    for lineup in lineups:
        by_team = defaultdict(int)

        for player in lineup.players:
            if player.position in {"RB", "WR", "TE"}:
                by_team[player.team] += 1

        for team, count in by_team.items():
            incidence[team] += 1

            if count >= 2:
                multi_incidence[team] += 1

    rows = []

    for team in sorted(incidence):
        rows.append(
            {
                "Team": team,
                "AnySkillLineupRate":
                    incidence[team] / n,
                "MultiSkillLineupRate":
                    multi_incidence[team] / n,
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(
            "MultiSkillLineupRate",
            ascending=False,
        )
    )


def portfolio_summary(
    lineups: list[Lineup],
) -> dict:
    if not lineups:
        return {}

    projections = [
        l.projection
        for l in lineups
    ]

    salaries = [
        l.salary
        for l in lineups
    ]

    overlap = pairwise_overlap_summary(lineups)

    return {
        "lineups": len(lineups),
        "mean_projection": float(
            np.mean(projections)
        ),
        "median_projection": float(
            np.median(projections)
        ),
        "p90_projection": float(
            np.percentile(projections, 90)
        ),
        "max_projection": float(
            max(projections)
        ),
        "mean_salary": float(
            np.mean(salaries)
        ),
        "mean_salary_left": float(
            np.mean(
                [
                    50_000 - x
                    for x in salaries
                ]
            )
        ),
        "effective_player_count":
            effective_player_count(lineups),
        "effective_qb_count":
            effective_qb_count(lineups),
        **overlap,
    }


def marginal_diversified_select(
    candidates: list[Lineup],
    target: int,
    *,
    overlap_penalty: float = 2.0,
    story_penalty: float = 1.0,
) -> list[Lineup]:
    """
    Transparent provisional selector.

    Projection remains the base score.

    Penalties only discourage repeatedly buying the same
    exact roster/story.

    This is NOT claimed to be an EV-optimal selector.
    """
    if target >= len(candidates):
        return list(candidates)

    remaining = list(candidates)
    selected: list[Lineup] = []

    projection_values = np.array(
        [x.projection for x in candidates],
        dtype=float,
    )

    p_min = float(projection_values.min())
    p_max = float(projection_values.max())

    def normalized_projection(lineup: Lineup) -> float:
        if p_max <= p_min:
            return 1.0

        return (
            lineup.projection - p_min
        ) / (
            p_max - p_min
        )

    story_counts = Counter()

    while remaining and len(selected) < target:
        best = None
        best_score = -math.inf

        for lineup in remaining:
            score = normalized_projection(lineup)

            if selected:
                max_overlap = max(
                    len(
                        lineup.player_ids
                        & prior.player_ids
                    )
                    for prior in selected
                )

                score -= (
                    overlap_penalty
                    * (max_overlap / 9.0)
                )

            story_count = story_counts[
                lineup.story_signature()
            ]

            if selected:
                score -= (
                    story_penalty
                    * story_count
                    / len(selected)
                )

            if score > best_score:
                best_score = score
                best = lineup

        selected.append(best)
        remaining.remove(best)

        story_counts[
            best.story_signature()
        ] += 1

    return selected


def allocate_three_contests(
    lineups: list[Lineup],
    contest_names: tuple[str, str, str] = (
        "First Down",
        "Quarter Jukebox",
        "Dime Package",
    ),
) -> dict[str, list[Lineup]]:
    """
    Simple balanced allocator for our recurring 3x20 workflow.

    Requires exactly 60 lineups.
    """
    if len(lineups) != 60:
        raise ValueError(
            "3x20 allocator requires exactly 60 lineups."
        )

    buckets = {
        name: []
        for name in contest_names
    }

    exposure = {
        name: Counter()
        for name in contest_names
    }

    qb_exposure = {
        name: Counter()
        for name in contest_names
    }

    ordered = sorted(
        lineups,
        key=lambda x: x.projection,
        reverse=True,
    )

    for lineup in ordered:
        eligible = [
            name
            for name in contest_names
            if len(buckets[name]) < 20
        ]

        best_name = None
        best_cost = math.inf

        for name in eligible:
            player_repeat_cost = sum(
                exposure[name][p.dk_id]
                for p in lineup.players
            )

            qb_repeat_cost = (
                qb_exposure[name][lineup.qb.dk_id]
                * 2
            )

            size_cost = len(buckets[name]) * 0.1

            cost = (
                player_repeat_cost
                + qb_repeat_cost
                + size_cost
            )

            if cost < best_cost:
                best_cost = cost
                best_name = name

        buckets[best_name].append(lineup)

        for p in lineup.players:
            exposure[best_name][p.dk_id] += 1

        qb_exposure[
            best_name
        ][lineup.qb.dk_id] += 1

    return buckets