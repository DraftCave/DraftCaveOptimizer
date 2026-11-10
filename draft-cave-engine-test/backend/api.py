from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from config import raw_baseline
from data_loader import (
    join_projections,
    load_dk_salaries,
    load_projection_table,
)
from optimizer import generate_lineups


class OptimizeRequest(BaseModel):
    num_lineups: int = Field(
        default=5,
        ge=1,
        le=2000,
    )

    minimum_uniques: int = Field(
        default=3,
        ge=1,
        le=9,
    )

    min_salary: int = Field(
        default=0,
        ge=0,
        le=50_000,
    )

    randomization_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    random_seed: int = Field(
        default=42,
        ge=0,
        le=2_147_483_647,
    )

    qb_stack_min: int = Field(
        default=0,
        ge=0,
        le=8,
    )

    qb_stack_max: int = Field(
        default=8,
        ge=0,
        le=8,
    )

    require_bringback: bool = False
    require_secondary_stack: bool = False

    sim_same_team_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    sim_opponent_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    projection_weight: float = Field(
        default=1.0,
        ge=0.0,
    )

    lock_players: list[int] = Field(
        default_factory=list,
    )

    exclude_players: list[int] = Field(
        default_factory=list,
    )

    player_max_exposure: dict[int, float] = Field(
        default_factory=dict,
    )

    player_min_exposure: dict[int, float] = Field(
        default_factory=dict,
    )

    position_player_caps: dict[str, float] = Field(
        default_factory=dict,
    )

    flex_position_caps: dict[str, float] = Field(
        default_factory=dict,
    )

    max_offense_vs_opposing_dst: int | None = Field(
        default=None,
        ge=0,
        le=8,
    )

    max_qb_with_same_team_dst: int | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    max_qb_with_same_team_rb: int | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    @model_validator(mode="after")
    def validate_request(self):
        if self.qb_stack_min > self.qb_stack_max:
            raise ValueError(
                "qb_stack_min must be less than or equal to qb_stack_max"
            )

        lock_set = set(self.lock_players)
        exclude_set = set(self.exclude_players)

        conflicts = sorted(
            lock_set.intersection(exclude_set)
        )

        if conflicts:
            conflict_text = ", ".join(
                str(dk_id)
                for dk_id in conflicts
            )

            raise ValueError(
                f"Players cannot be both locked and excluded: {conflict_text}"
            )

        for dk_id, exposure in self.player_max_exposure.items():
            if exposure < 0.0 or exposure > 1.0:
                raise ValueError(
                    f"player_max_exposure for {dk_id} must be between 0.0 and 1.0"
                )

        for dk_id, exposure in self.player_min_exposure.items():
            if exposure < 0.0 or exposure > 1.0:
                raise ValueError(
                    f"player_min_exposure for {dk_id} must be between 0.0 and 1.0"
                )

            if dk_id in self.player_max_exposure:
                max_exposure = self.player_max_exposure[dk_id]

                if exposure > max_exposure:
                    raise ValueError(
                        f"player_min_exposure for {dk_id} must be less than or equal to player_max_exposure"
                    )

        valid_positions = {
            "QB",
            "RB",
            "WR",
            "TE",
            "DST",
        }

        for position, exposure in self.position_player_caps.items():
            if position not in valid_positions:
                raise ValueError(
                    f"position_player_caps contains unsupported position: {position}"
                )

            if exposure < 0.0 or exposure > 1.0:
                raise ValueError(
                    f"position_player_caps for {position} must be between 0.0 and 1.0"
                )

        valid_flex_positions = {
            "RB",
            "WR",
            "TE",
        }

        for position, exposure in self.flex_position_caps.items():
            if position not in valid_flex_positions:
                raise ValueError(
                    f"flex_position_caps contains unsupported position: {position}"
                )

            if exposure < 0.0 or exposure > 1.0:
                raise ValueError(
                    f"flex_position_caps for {position} must be between 0.0 and 1.0"
                )

        return self


app = FastAPI(
    title="Draft Cave API",
    version="0.32.0",
)


def serialize_lineups(lineups):
    return [
        {
            "total_salary": lineup.salary,
            "total_projection": lineup.projection,
            "players": {
                slot: {
                    "dk_id": player.dk_id,
                    "name": player.name,
                    "team": player.team,
                    "opponent": player.opponent,
                    "position": player.position,
                    "salary": player.salary,
                    "projection": player.projection,
                }
                for slot, player in lineup.slots.items()
            },
        }
        for lineup in lineups
    ]


def validate_player_ids(
    request: OptimizeRequest,
    players,
):
    valid_ids = {
        player.dk_id
        for player in players
    }

    referenced_ids = (
        set(request.lock_players)
        | set(request.exclude_players)
        | set(request.player_max_exposure)
        | set(request.player_min_exposure)
    )

    unknown_ids = sorted(
        referenced_ids - valid_ids
    )

    if unknown_ids:
        unknown_text = ", ".join(
            str(dk_id)
            for dk_id in unknown_ids
        )

        raise HTTPException(
            status_code=422,
            detail=(
                "Unknown DraftKings player IDs "
                f"for the current slate: {unknown_text}"
            ),
        )


@app.get("/")
def root():
    return {
        "name": "Draft Cave API",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


@app.get("/players")
def get_players():
    dk_file = "data/DKSalaries.csv"
    projection_file = "data/projections.csv"

    dk_players = load_dk_salaries(
        dk_file
    )

    projections = load_projection_table(
        projection_file
    )

    players, join_report = join_projections(
        dk_players,
        projections,
        source_name="local_projection_file",
    )

    sorted_players = sorted(
        players,
        key=lambda player: (
            -player.salary,
            player.name,
        ),
    )

    players_with_projection = sum(
        1
        for player in sorted_players
        if player.projection is not None
    )

    players_missing_projection = (
        len(sorted_players)
        - players_with_projection
    )

    return {
        "matched_projection_rows": int(
            join_report["status"]
            .eq("MATCHED")
            .sum()
        ),
        "unresolved_rows": int(
            join_report["status"]
            .eq("UNRESOLVED")
            .sum()
        ),
        "player_count": len(
            sorted_players
        ),
        "players_with_projection": (
            players_with_projection
        ),
        "players_missing_projection": (
            players_missing_projection
        ),
        "players": [
            {
                "dk_id": player.dk_id,
                "name": player.name,
                "position": player.position,
                "team": player.team,
                "opponent": player.opponent,
                "salary": player.salary,
                "projection": player.projection,
            }
            for player in sorted_players
        ],
    }


@app.get("/test-optimize")
def test_optimize():
    dk_file = "data/DKSalaries.csv"
    projection_file = "data/projections.csv"

    dk_players = load_dk_salaries(
        dk_file
    )

    projections = load_projection_table(
        projection_file
    )

    players, join_report = join_projections(
        dk_players,
        projections,
        source_name="local_projection_file",
    )

    settings = raw_baseline()
    settings.num_lineups = 5
    settings.minimum_uniques = 3

    result = generate_lineups(
        players,
        settings,
    )

    return {
        "matched_projection_rows": int(
            join_report["status"]
            .eq("MATCHED")
            .sum()
        ),
        "unresolved_rows": int(
            join_report["status"]
            .eq("UNRESOLVED")
            .sum()
        ),
        "requested_lineups": 5,
        "generated_lineups": len(
            result.lineups
        ),
        "warnings": result.warnings,
        "lineups": serialize_lineups(
            result.lineups
        ),
    }


@app.post("/optimize")
def optimize(request: OptimizeRequest):
    dk_file = "data/DKSalaries.csv"
    projection_file = "data/projections.csv"

    dk_players = load_dk_salaries(
        dk_file
    )

    projections = load_projection_table(
        projection_file
    )

    players, join_report = join_projections(
        dk_players,
        projections,
        source_name="local_projection_file",
    )

    validate_player_ids(
        request,
        players,
    )

    settings = raw_baseline()

    settings.num_lineups = (
        request.num_lineups
    )

    settings.minimum_uniques = (
        request.minimum_uniques
    )

    settings.minimum_salary = (
        request.min_salary
    )

    settings.randomization_pct = (
        request.randomization_pct
    )

    settings.random_seed = (
        request.random_seed
    )

    settings.qb_stack_min = (
        request.qb_stack_min
    )

    settings.qb_stack_max = (
        request.qb_stack_max
    )

    settings.require_bringback = (
        request.require_bringback
    )

    settings.require_secondary_stack = (
        request.require_secondary_stack
    )

    settings.sim_same_team_pct = (
        request.sim_same_team_pct
    )

    settings.sim_opponent_pct = (
        request.sim_opponent_pct
    )

    settings.projection_weight = (
        request.projection_weight
    )

    settings.lock_players = set(
        request.lock_players
    )

    settings.exclude_players = set(
        request.exclude_players
    )

    settings.player_max_exposure = dict(
        request.player_max_exposure
    )

    settings.player_min_exposure = dict(
        request.player_min_exposure
    )

    for (
        position,
        exposure,
    ) in request.position_player_caps.items():
        settings.position_player_caps[
            position
        ] = exposure

    for (
        position,
        exposure,
    ) in request.flex_position_caps.items():
        settings.flex_position_caps[
            position
        ] = exposure

    settings.max_offense_vs_opposing_dst = (
        request.max_offense_vs_opposing_dst
    )

    settings.max_qb_with_same_team_dst = (
        request.max_qb_with_same_team_dst
    )

    settings.max_qb_with_same_team_rb = (
        request.max_qb_with_same_team_rb
    )

    result = generate_lineups(
        players,
        settings,
    )

    return {
        "matched_projection_rows": int(
            join_report["status"]
            .eq("MATCHED")
            .sum()
        ),
        "unresolved_rows": int(
            join_report["status"]
            .eq("UNRESOLVED")
            .sum()
        ),
        "requested_lineups": (
            request.num_lineups
        ),
        "minimum_uniques": (
            request.minimum_uniques
        ),
        "min_salary": (
            request.min_salary
        ),
        "randomization_pct": (
            request.randomization_pct
        ),
        "random_seed": (
            request.random_seed
        ),
        "qb_stack_min": (
            request.qb_stack_min
        ),
        "qb_stack_max": (
            request.qb_stack_max
        ),
        "require_bringback": (
            request.require_bringback
        ),
        "require_secondary_stack": (
            request.require_secondary_stack
        ),
        "sim_same_team_pct": (
            request.sim_same_team_pct
        ),
        "sim_opponent_pct": (
            request.sim_opponent_pct
        ),
        "projection_weight": (
            request.projection_weight
        ),
        "lock_players": (
            request.lock_players
        ),
        "exclude_players": (
            request.exclude_players
        ),
        "player_max_exposure": (
            request.player_max_exposure
        ),
        "player_min_exposure": (
            request.player_min_exposure
        ),
        "position_player_caps": (
            request.position_player_caps
        ),
        "flex_position_caps": (
            request.flex_position_caps
        ),
        "max_offense_vs_opposing_dst": (
            request.max_offense_vs_opposing_dst
        ),
        "max_qb_with_same_team_dst": (
            request.max_qb_with_same_team_dst
        ),
        "max_qb_with_same_team_rb": (
            request.max_qb_with_same_team_rb
        ),
        "generated_lineups": len(
            result.lineups
        ),
        "warnings": result.warnings,
        "lineups": serialize_lineups(
            result.lineups
        ),
    }