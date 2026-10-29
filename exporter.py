from __future__ import annotations

import pandas as pd

from models import Lineup


DK_EXPORT_COLUMNS = (
    "QB",
    "RB",
    "RB",
    "WR",
    "WR",
    "WR",
    "TE",
    "FLEX",
    "DST",
)


def lineup_to_dk_row(lineup: Lineup) -> list[str]:
    return [
        lineup.slots["QB"].name_id,
        lineup.slots["RB1"].name_id,
        lineup.slots["RB2"].name_id,
        lineup.slots["WR1"].name_id,
        lineup.slots["WR2"].name_id,
        lineup.slots["WR3"].name_id,
        lineup.slots["TE"].name_id,
        lineup.slots["FLEX"].name_id,
        lineup.slots["DST"].name_id,
    ]


def lineups_to_dk_dataframe(
    lineups: list[Lineup],
) -> pd.DataFrame:
    rows = [
        lineup_to_dk_row(lineup)
        for lineup in lineups
    ]

    return pd.DataFrame(
        rows,
        columns=list(DK_EXPORT_COLUMNS),
    )


def export_lineups_csv(
    lineups: list[Lineup],
    path: str,
) -> None:
    df = lineups_to_dk_dataframe(lineups)

    df.to_csv(
        path,
        index=False,
    )