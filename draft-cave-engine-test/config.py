from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OptimizerSettings:
    # Reservoir
    num_lineups: int = 60

    # DraftKings legality
    salary_cap: int = 50_000
    minimum_salary: int = 0
    minimum_uniques: int = 3

    # Player pool
    min_player_projection: float = 0.01
    exclude_zero_projection: bool = True

    # Candidate discovery
    randomization_pct: float = 0.0
    random_seed: int = 42

    # Primary QB construction
    qb_stack_min: int = 0
    qb_stack_max: int = 8
    require_bringback: bool = False

    # Secondary stack
    require_secondary_stack: bool = False

    # Correlation objective boosts
    sim_same_team_pct: float = 0.0
    sim_opponent_pct: float = 0.0

    # Optional DST / QB-RB restrictions
    max_offense_vs_opposing_dst: int | None = None
    max_qb_with_same_team_dst: int | None = None
    max_qb_with_same_team_rb: int | None = None

    # Market constraints
    ownership_min: float | None = None
    ownership_max: float | None = None

    # Per-player default caps by position.
    # 1.00 means unrestricted.
    position_player_caps: dict[str, float] = field(
        default_factory=lambda: {
            "QB": 1.00,
            "RB": 1.00,
            "WR": 1.00,
            "TE": 1.00,
            "DST": 1.00,
        }
    )

    # FLEX distribution caps across generated lineups.
    flex_position_caps: dict[str, float] = field(
        default_factory=lambda: {
            "RB": 1.00,
            "WR": 1.00,
            "TE": 1.00,
        }
    )

    # Player-specific exposure overrides keyed by DK ID.
    player_max_exposure: dict[int, float] = field(default_factory=dict)
    player_min_exposure: dict[int, float] = field(default_factory=dict)

    # Explicit pool controls.
    lock_players: set[int] = field(default_factory=set)
    exclude_players: set[int] = field(default_factory=set)

    # Transparent objective blend.
    projection_weight: float = 1.0
    ceiling_weight: float = 0.0

    # Optional StatRankings objective influence; never mutate Player.projection.
    # OFF = 0%; LOW = max +/-0.5%; MEDIUM = max +/-1.0%; HIGH = max +/-2.0%.
    statrankings_influence: str = "OFF"
    # Evidence edges expected on a -8 to +8 scale, keyed by DK ID.
    statrankings_edge_by_id: dict[int, float] = field(default_factory=dict)

    # Manual player conviction / sentiment layer.
    # This is an optimizer-objective intervention only and never mutates
    # Player.projection. Values are keyed by DraftKings ID.
    player_sentiment_by_id: dict[int, str] = field(default_factory=dict)


def raw_baseline() -> OptimizerSettings:
    """
    Completely neutral Draft Cave diagnostic baseline.

    Deliberately does not encode historical Draft Cave settings as laws.
    """
    return OptimizerSettings()


def discovery_example() -> OptimizerSettings:
    """
    Research preset inspired by recent Draft Cave candidate discovery.

    This is NOT a permanent methodology default.
    """
    return OptimizerSettings(
        num_lineups=60,
        minimum_uniques=3,
        randomization_pct=0.20,
        qb_stack_min=1,
        qb_stack_max=2,
        sim_same_team_pct=0.20,
        sim_opponent_pct=0.07,
    )