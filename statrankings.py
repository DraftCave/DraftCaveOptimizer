from __future__ import annotations

import csv
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from models import Player


COLUMNS = (
    "DK_ID", "Player", "Team", "Position", "SR_AsOf", "DK_FPPG",
    "DK_FPPG_L5", "Role_Score", "Form_Score", "Matchup_Score",
    "Environment_Score", "Edge_Score", "Role_Reason", "Form_Reason",
    "Matchup_Reason", "Environment_Reason",
)
NUMERIC = COLUMNS[5:12]


@dataclass
class Snapshot:
    status: str
    evidence_by_id: dict[int, dict] = field(default_factory=dict)
    unresolved: list[dict] = field(default_factory=list)

    @property
    def edge_by_id(self) -> dict[int, float]:
        return {pid: row["Edge_Score"] for pid, row in self.evidence_by_id.items()
                if row["Edge_Score"] is not None}


def _normalize(value: str) -> str:
    # Conservative normalization: no nicknames, punctuation removal, or aliases.
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def load_snapshot(path: str | Path, players: list[Player]) -> Snapshot:
    """Load optional evidence without modifying slate identity or projections.

    Missing numeric cells (blank/NA/NaN/None/null) remain None. Invalid numbers,
    nonfinite values and out-of-range scores reject the entire evidence row.
    CSV row numbers are retained for actionable rejection reports.
    """
    result = Snapshot("Local file")
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)) or set(COLUMNS) - set(headers):
                return Snapshot("Invalid file", unresolved=[{
                    "Row": 1, "Reason": "Missing required or duplicate CSV columns"}])
            rows = list(reader)
    except FileNotFoundError:
        return Snapshot("Missing")
    except (OSError, UnicodeError, csv.Error) as exc:
        return Snapshot("Invalid file", unresolved=[{"Reason": str(exc)}])

    by_id, by_key = defaultdict(list), defaultdict(list)
    for player in players:
        by_id[player.dk_id].append(player)
        by_key[tuple(_normalize(v) for v in
                     (player.name, player.team, player.position))].append(player)

    id_rows = defaultdict(list)
    for index, row in enumerate(rows):
        raw_id = (row.get("DK_ID") or "").strip()
        if re.fullmatch(r"[0-9]+", raw_id):
            id_rows[int(raw_id)].append(index)
    duplicate_conflicts = set()
    for indices in id_rows.values():
        if any(rows[i] != rows[indices[0]] for i in indices):
            duplicate_conflicts.update(indices)

    candidates = defaultdict(list)
    def reject(index, reason):
        row = rows[index]
        result.unresolved.append({"Row": index + 2, "DK_ID": row.get("DK_ID"),
                                  "Player": row.get("Player"), "Reason": reason})

    for index, row in enumerate(rows):
        if index in duplicate_conflicts:
            reject(index, "Conflicting duplicate DK_ID evidence")
            continue
        if None in row or any(row.get(c) is None for c in COLUMNS):
            reject(index, "Malformed CSV row")
            continue
        raw_id = row["DK_ID"].strip()
        if raw_id:
            if not re.fullmatch(r"[0-9]+", raw_id) or int(raw_id) <= 0:
                reject(index, "Invalid DK_ID; fallback prohibited")
                continue
            matches = by_id[int(raw_id)]
        else:
            key = tuple(_normalize(row[c]) for c in ("Player", "Team", "Position"))
            matches = by_key[key] if all(key) else []
        if len(matches) != 1 or len(by_id[matches[0].dk_id]) != 1:
            reject(index, "Unmatched or ambiguous current-slate identity")
            continue
        player = matches[0]
        if any(_normalize(row[c]) != _normalize(expected)
               for c, expected in (("Team", player.team), ("Position", player.position))):
            reject(index, "Team or position missing/conflicts with current slate")
            continue
        evidence = {c: row[c].strip() or None for c in COLUMNS}
        try:
            for column in NUMERIC:
                value = evidence[column]
                if value is None or value.casefold() in {"na", "nan", "none", "null"}:
                    evidence[column] = None
                    continue
                number = float(value)
                limit = 8 if column == "Edge_Score" else 2
                if not math.isfinite(number) or (column.endswith("_Score") and abs(number) > limit):
                    raise ValueError(f"{column} is nonfinite or outside [-{limit}, +{limit}]")
                evidence[column] = number
        except ValueError as exc:
            reject(index, f"Invalid numeric evidence: {exc}")
            continue
        candidates[player.dk_id].append((index, evidence))

    for pid, entries in candidates.items():
        # A fallback row must not bypass conflicting explicit-ID evidence.
        blocked = any(i in duplicate_conflicts for i in id_rows[pid])
        if blocked or any(rows[i] != rows[entries[0][0]] for i, _ in entries):
            for index, _ in entries:
                reject(index, "Conflicting evidence rows resolve to the same DK player")
        else:
            result.evidence_by_id[pid] = entries[0][1]
    return result
