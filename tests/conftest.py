"""Isolated synthetic files for integration tests; no private slate required."""
from pathlib import Path

import pandas as pd
import pytest
from test_optimizer import synthetic_pool


def write_test_slate(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    players = synthetic_pool()
    pd.DataFrame([{
        "Position": p.position, "Name + ID": p.name_id, "Name": p.name,
        "ID": p.dk_id, "Roster Position": "/".join(p.roster_positions),
        "Salary": p.salary, "Game Info": p.game, "TeamAbbrev": p.team,
        "Status": "",
    } for p in players]).to_csv(directory / "DKSalaries.csv", index=False)
    pd.DataFrame([{
        "Name": p.name, "Team": p.team, "Position": p.position,
        "Projection": p.projection,
    } for p in players]).to_csv(directory / "projections.csv", index=False)


@pytest.fixture
def slate_dir(tmp_path):
    write_test_slate(tmp_path / "data")
    return tmp_path / "data"
