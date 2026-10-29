from __future__ import annotations

import re
from dataclasses import replace
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
    """
    Reads a generic projection CSV.

    Supported examples include:

    Draft Cave / DS:
        Name, Points, ProjOwn, CeilingPoints

    Generic:
        Name, Team, Position, Projection, Ownership, Ceiling

    StatRankings-like:
        name, team, position, fantasy_points, ownership
    """
    df = pd.read_csv(path_or_buffer)

    name_col = _find_column(
        df.columns,
        ["Name", "Player", "player_name"],
    )

    projection_col = _find_column(
        df.columns,
        [
            "Projection",
            "Points",
            "Fantasy Points",
            "fantasy_points",
            "Fpts",
        ],
    )

    team_col = _find_column(
        df.columns,
        ["Team", "TeamAbbrev", "team_abbrev"],
    )

    position_col = _find_column(
        df.columns,
        ["Position", "Pos"],
    )

    ownership_col = _find_column(
        df.columns,
        [
            "Ownership",
            "ProjOwn",
            "Projected Ownership %",
            "projected_ownership",
        ],
    )

    ceiling_col = _find_column(
        df.columns,
        [
            "Ceiling",
            "CeilingPoints",
            "Ceiling Points",
        ],
    )

    if name_col is None:
        raise ValueError(
            "Projection file must contain a player Name column."
        )

    if projection_col is None:
        raise ValueError(
            "Projection file must contain a projection/Points column."
        )

    out = pd.DataFrame()

    out["name"] = df[name_col].astype(str).str.strip()
    out["normalized_name"] = out["name"].map(normalize_name)

    out["projection"] = pd.to_numeric(
        df[projection_col],
        errors="coerce",
    )

    if team_col is not None:
        out["team"] = (
            df[team_col]
            .astype(str)
            .str.strip()
            .str.upper()
        )
    else:
        out["team"] = None

    if position_col is not None:
        out["position"] = (
            df[position_col]
            .astype(str)
            .str.strip()
            .str.upper()
        )
    else:
        out["position"] = None

    if ownership_col is not None:
        ownership = pd.to_numeric(
            df[ownership_col],
            errors="coerce",
        )

        if ownership.notna().any() and (ownership.fillna(0) == 0).all():
            out["ownership"] = None
        else:
            out["ownership"] = ownership
    else:
        out["ownership"] = None

    if ceiling_col is not None:
        ceiling = pd.to_numeric(
            df[ceiling_col],
            errors="coerce",
        )

        if ceiling.notna().any() and (ceiling.fillna(0) == 0).all():
            out["ceiling"] = None
        else:
            out["ceiling"] = ceiling
    else:
        out["ceiling"] = None

    return out


def join_projections(
    players: list[Player],
    projections: pd.DataFrame,
    *,
    source_name: str = "projection_csv",
    aliases: dict[str, str] | None = None,
) -> tuple[list[Player], pd.DataFrame]:
    """
    Strict identity resolution.

    No fuzzy auto-match.

    Match order:
      1. normalized exact Name + Team
      2. normalized exact Name if unique in DK
      3. explicit aliases
      4. unresolved
    """
    aliases = aliases or {}

    dk_by_name_team: dict[tuple[str, str], Player] = {}
    dk_by_name: dict[str, list[Player]] = {}

    for p in players:
        norm = normalize_name(p.name)

        dk_by_name_team[(norm, p.team)] = p
        dk_by_name.setdefault(norm, []).append(p)

    updates: dict[int, dict] = {}
    report_rows: list[dict] = []

    for _, row in projections.iterrows():
        raw_name = row["name"]
        norm = normalize_name(raw_name)

        if norm in aliases:
            norm = normalize_name(aliases[norm])

        team = row.get("team")

        if pd.isna(team):
            team = None

        if team:
            team = str(team).strip().upper()

        matched: Player | None = None
        method = None

        if team:
            matched = dk_by_name_team.get((norm, team))

            if matched is not None:
                method = "exact_name_team"

        if matched is None:
            candidates = dk_by_name.get(norm, [])

            if len(candidates) == 1:
                matched = candidates[0]
                method = "unique_exact_name"

        if matched is None:
            report_rows.append(
                {
                    "projection_name": raw_name,
                    "team": team,
                    "status": "UNRESOLVED",
                    "match_method": None,
                    "dk_id": None,
                    "dk_name": None,
                }
            )
            continue

        updates[matched.dk_id] = {
            "projection": (
                None
                if pd.isna(row["projection"])
                else float(row["projection"])
            ),
            "ceiling": (
                None
                if pd.isna(row["ceiling"])
                else float(row["ceiling"])
            ),
            "ownership": (
                None
                if pd.isna(row["ownership"])
                else float(row["ownership"])
            ),
        }

        report_rows.append(
            {
                "projection_name": raw_name,
                "team": team,
                "status": "MATCHED",
                "match_method": method,
                "dk_id": matched.dk_id,
                "dk_name": matched.name,
            }
        )

    joined: list[Player] = []

    for player in players:
        values = updates.get(player.dk_id)

        if values is None:
            joined.append(player)
            continue

        joined.append(
            replace(
                player,
                projection=values["projection"],
                ceiling=values["ceiling"],
                ownership=values["ownership"],
                source_projection=source_name,
                source_ceiling=(
                    source_name
                    if values["ceiling"] is not None
                    else None
                ),
                source_ownership=(
                    source_name
                    if values["ownership"] is not None
                    else None
                ),
            )
        )

    report = pd.DataFrame(report_rows)

    return joined, report