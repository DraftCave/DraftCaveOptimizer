from __future__ import annotations

import re
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Iterable

import pandas as pd

from models import Player


def normalize_name(value: str) -> str:
    value = str(value).strip().lower()

    value = value.replace("’", "'")
    value = value.replace(".", "")
    value = value.replace("-", " ")

    value = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", value)

    value = re.sub(r"[^a-z0-9 ]+", "", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value


def parse_game_info(game_info: str, team: str) -> tuple[str, str]:
    """
    DK format example:
        BAL@BUF 11/01/2026 01:00PM ET

    Returns:
        game_key, opponent
    """
    matchup = str(game_info).split()[0].strip()

    if "@" not in matchup:
        raise ValueError(f"Unable to parse Game Info: {game_info!r}")

    away, home = matchup.split("@", 1)

    away = away.upper()
    home = home.upper()
    team = team.upper()

    if team == away:
        opponent = home
    elif team == home:
        opponent = away
    else:
        raise ValueError(
            f"Team {team} is not present in matchup {matchup}"
        )

    return matchup, opponent


def load_dk_salaries(path_or_buffer) -> list[Player]:
    df = pd.read_csv(path_or_buffer)

    required = {
        "Position",
        "Name + ID",
        "Name",
        "ID",
        "Roster Position",
        "Salary",
        "Game Info",
        "TeamAbbrev",
        "Status",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"DraftKings salary file missing required columns: "
            f"{sorted(missing)}"
        )

    if df["ID"].duplicated().any():
        dupes = df.loc[df["ID"].duplicated(), "ID"].tolist()
        raise ValueError(f"Duplicate DraftKings IDs found: {dupes}")

    players: list[Player] = []

    for _, row in df.iterrows():
        team = str(row["TeamAbbrev"]).strip().upper()

        game, opponent = parse_game_info(
            row["Game Info"],
            team,
        )

        roster_positions = tuple(
            str(row["Roster Position"])
            .replace("/", ",")
            .split(",")
        )

        roster_positions = tuple(
            x.strip().upper()
            for x in roster_positions
            if x.strip()
        )

        status = row["Status"]

        if pd.isna(status):
            status = None
        else:
            status = str(status).strip().upper() or None

        players.append(
            Player(
                dk_id=int(row["ID"]),
                name=str(row["Name"]).strip(),
                name_id=str(row["Name + ID"]).strip(),
                position=str(row["Position"]).strip().upper(),
                roster_positions=roster_positions,
                salary=int(row["Salary"]),
                team=team,
                opponent=opponent,
                game=game,
                status=status,
            )
        )

    return players


def _find_column(
    columns: Iterable[str],
    candidates: list[str],
) -> str | None:
    lookup = {
        str(col).strip().lower(): col
        for col in columns
    }

    for candidate in candidates:
        key = candidate.lower()

        if key in lookup:
            return lookup[key]

    return None


def load_projection_table(path_or_buffer) -> pd.DataFrame:
    """Normalize feed columns without filling missing model values."""
    df = pd.read_csv(path_or_buffer, dtype=str)
    fields = {
        "dk_id": ["DK_ID", "DK ID", "DraftKings ID"],
        "name": ["Name", "Player", "player_name"],
        "team": ["Team", "TeamAbbrev", "team_abbrev"],
        "position": ["Position", "Pos"],
        "projection": ["Projection", "Points", "Fantasy Points", "fantasy_points", "Fpts"],
        "ownership": ["DC Own", "DC_Own", "ProjOwn", "Ownership", "Projected Ownership %", "projected_ownership"],
        "ceiling": ["DC Ceiling", "DC_Ceiling", "CeilingPoints", "Ceiling", "Ceiling Points"],
        "eligibility_state": ["eligibility_state", "Eligibility State", "Eligibility", "DC Eligibility"],
    }
    columns = {key: _find_column(df.columns, aliases) for key, aliases in fields.items()}
    if columns["dk_id"] is None and columns["name"] is None:
        raise ValueError("Projection file must contain DK_ID or Name.")
    if columns["projection"] is None:
        raise ValueError("Projection file must contain a projection/Points column.")
    out = pd.DataFrame(index=df.index)
    for key, col in columns.items():
        values = df[col].str.strip().replace("", None) if col else pd.Series(None, index=df.index, dtype=object)
        if key in {"projection", "ownership", "ceiling"}:
            values = pd.to_numeric(values, errors="coerce").replace([float('inf'), -float('inf')], float('nan'))
        elif key in {"team", "position", "eligibility_state"}:
            values = values.str.upper() if col else values
        out[key] = values
    out["normalized_name"] = out["name"].map(lambda v: normalize_name(v) if pd.notna(v) else None)
    return out


def join_projections(players, projections, *, source_name="projection_csv", aliases=None):
    """DK identity is authoritative. IDs never fall back to names.

    The legacy aliases argument is retained for call compatibility but aliases
    cannot override exact normalized identity matching.
    """
    by_id = {p.dk_id: p for p in players}
    updates = {}
    report = []
    def present(value):
        return value is not None and pd.notna(value) and str(value).strip() != ""
    for _, row in projections.iterrows():
        raw_id, name = row.get("dk_id"), row.get("name")
        team, position = row.get("team"), row.get("position")
        team = str(team).strip().upper() if present(team) else None
        position = str(position).strip().upper() if present(position) else None
        matched, method = None, None
        if present(raw_id):
            try:
                number = Decimal(str(raw_id))
                if not number.is_finite() or number != number.to_integral_value() or number <= 0:
                    raise ValueError()
                dk_id = int(number)
            except (ValueError, InvalidOperation):
                raise ValueError(f"Invalid DK_ID: {raw_id!r}") from None
            matched = by_id.get(dk_id)
            method = "dk_id"
        elif present(name):
            candidates = [p for p in players if normalize_name(p.name) == normalize_name(name)]
            if team:
                candidates = [p for p in candidates if p.team == team]
            if position:
                candidates = [p for p in candidates if p.position == position]
            if len(candidates) == 1:
                matched = candidates[0]
                method = "exact_name_team" if team else "unique_exact_name"
        if matched:
            if (team and team != matched.team) or (position and position != matched.position):
                raise ValueError(f"DK_ID {matched.dk_id} conflicts with DK salary team or position")
            if matched.dk_id in updates:
                raise ValueError(f"Duplicate feed assignment for DK_ID {matched.dk_id}")
            values = {key: float(row[key]) if present(row.get(key)) else None
                      for key in ("projection", "ownership", "ceiling")}
            state = row.get("eligibility_state")
            values["eligibility_state"] = str(state).strip().upper() if present(state) else None
            for key in ("projection", "ownership", "ceiling"):
                values["source_" + key] = source_name if values[key] is not None else None
            updates[matched.dk_id] = values
        report.append({"projection_name": name, "team": team,
                       "status": "MATCHED" if matched else "UNRESOLVED",
                       "match_method": method if matched else None,
                       "dk_id": matched.dk_id if matched else None,
                       "dk_name": matched.name if matched else None})
    return ([replace(p, **updates[p.dk_id]) if p.dk_id in updates else p for p in players],
            pd.DataFrame(report, columns=["projection_name", "team", "status", "match_method", "dk_id", "dk_name"]))
