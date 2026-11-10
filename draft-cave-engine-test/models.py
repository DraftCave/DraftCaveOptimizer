from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Player:
    dk_id: int
    name: str
    name_id: str
    position: str
    roster_positions: tuple[str, ...]
    salary: int
    team: str
    opponent: str
    game: str
    status: Optional[str]

    projection: Optional[float] = None
    ceiling: Optional[float] = None
    ownership: Optional[float] = None

    source_projection: Optional[str] = None
    source_ceiling: Optional[str] = None
    source_ownership: Optional[str] = None


@dataclass
class Lineup:
    slots: dict[str, Player]

    @property
    def players(self) -> list[Player]:
        return list(self.slots.values())

    @property
    def player_ids(self) -> frozenset[int]:
        return frozenset(p.dk_id for p in self.players)

    @property
    def salary(self) -> int:
        return sum(p.salary for p in self.players)

    @property
    def projection(self) -> float:
        return sum((p.projection or 0.0) for p in self.players)

    @property
    def ceiling(self) -> Optional[float]:
        values = [p.ceiling for p in self.players]

        if any(v is None for v in values):
            return None

        return float(sum(values))

    @property
    def ownership(self) -> Optional[float]:
        values = [p.ownership for p in self.players]

        if any(v is None for v in values):
            return None

        return float(sum(values))

    @property
    def qb(self) -> Player:
        return self.slots["QB"]

    @property
    def flex(self) -> Player:
        return self.slots["FLEX"]

    def story_signature(self) -> tuple:
        qb = self.qb

        same_team_pass = tuple(
            sorted(
                p.dk_id
                for p in self.players
                if p.team == qb.team
                and p.position in {"WR", "TE"}
            )
        )

        bringbacks = tuple(
            sorted(
                p.dk_id
                for p in self.players
                if p.team == qb.opponent
                and p.position in {"RB", "WR", "TE"}
            )
        )

        return (
            qb.dk_id,
            same_team_pass,
            bringbacks,
        )


@dataclass
class GenerationResult:
    lineups: list[Lineup]
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)