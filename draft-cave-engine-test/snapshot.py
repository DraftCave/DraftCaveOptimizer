import csv
import math
from dataclasses import replace
import pandas as pd
from data_loader import load_dk_salaries


def metric(raw):
    if raw == "":
        return None
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Invalid snapshot metric")
    return value


def verified_players(directory, snapshot_name="verified-ds-rs.csv", source_label="DS 2026-11-11 09:00 CT"):
    official = {p.dk_id: p for p in load_dk_salaries(directory / "DKSalaries.csv")}
    players = []
    with (directory / snapshot_name).open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            p = official.pop(int(row["DK_ID"]))
            if (p.name, p.team, p.position, p.salary, p.game) != (
                row["Name"], row["Team"], row["Position"], int(row["Salary"]), row["Game"].split()[0]
            ):
                raise ValueError("Snapshot identity conflict")
            projection, ceiling, ownership = (metric(row[k]) for k in ("Projection", "Ceiling", "Ownership"))
            if row["Eligible"] not in {"0", "1"} or (ownership is not None and ownership > 100):
                raise ValueError("Invalid snapshot classification")
            eligible = row["Eligible"] == "1"
            if eligible and (not projection or projection <= .1 or p.status in {"IR", "OUT", "O", "D", "HOLD", "EXCLUDE"}):
                raise ValueError("Invalid eligible player")
            players.append(replace(p, projection=projection, ceiling=ceiling, ownership=ownership,
                                   eligible=eligible, source_projection=source_label))
    if official or len(players) != 506:
        raise ValueError("Incomplete Week 10 snapshot")
    return players, pd.DataFrame({"status": ["MATCHED"] * len(players)})
