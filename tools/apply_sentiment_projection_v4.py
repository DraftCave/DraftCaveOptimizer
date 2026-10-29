from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(
            f"Could not find {label}; local app.py may differ from the expected checkpoint."
        )
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8")

# Import the canonical sentiment weights used by the optimizer itself.
app = replace_once(
    app,
    "from optimizer import generate_lineups\n",
    "from optimizer import generate_lineups, PLAYER_SENTIMENT_ADJUSTMENT\n",
    "optimizer import",
)

# Replace the Player Pool display math so Proj / Value reflect manual sentiment.
old_block = '''        value_score = None\n\n        if (\n            p.projection is not None\n            and p.salary\n        ):\n            value_score = (\n                float(p.projection)\n                / float(p.salary)\n                * 1000.0\n            )\n\n        pool_rows.append(\n            {'''

new_block = '''        # Presentation-only sentiment projection. The canonical source\n        # projection on the Player object is never mutated. This mirrors the\n        # manual sentiment multiplier used in optimizer.py so the Player Pool\n        # visually reflects the user's conviction. BAN remains an exclusion\n        # instruction and does not rewrite projection to zero.\n        base_projection = float(p.projection) if p.projection is not None else None\n        sentiment_state = str(controls.get("Sentiment", "NEUTRAL")).upper()\n        sentiment_adjustment = PLAYER_SENTIMENT_ADJUSTMENT.get(sentiment_state, 0.0)\n        if sentiment_adjustment is None:\n            sentiment_adjustment = 0.0\n        display_projection = (\n            base_projection * (1.0 + float(sentiment_adjustment))\n            if base_projection is not None\n            else None\n        )\n\n        value_score = None\n        if display_projection is not None and p.salary:\n            value_score = (\n                display_projection\n                / float(p.salary)\n                * 1000.0\n            )\n\n        pool_rows.append(\n            {'''

app = replace_once(app, old_block, new_block, "Player Pool value-score block")

app = replace_once(
    app,
    '''                "Proj": p.projection,''',
    '''                "Proj": display_projection,\n                "Base Proj": base_projection,''',
    "Player Pool projection row value",
)

# Preserve source projection as an optional research column for auditability.
app = replace_once(
    app,
    '''        "Own %", "Ceiling", "Value", "Sentiment", "Min %", "Max %", "ID",\n        "Role", "Form", "Matchup", "Env", "Edge", "Injury", "Status",''',
    '''        "Own %", "Ceiling", "Value", "Sentiment", "Min %", "Max %", "ID",\n        "Base Proj", "Role", "Form", "Matchup", "Env", "Edge", "Injury", "Status",''',
    "Player Pool dataframe columns",
)

app = replace_once(
    app,
    '''        display_columns += ["ID", "Role", "Form", "Matchup", "Env", "Edge", "Injury", "Status"]''',
    '''        display_columns += ["ID", "Base Proj", "Role", "Form", "Matchup", "Env", "Edge", "Injury", "Status"]''',
    "research display columns",
)

app = replace_once(
    app,
    '''            "Proj",\n            "Own %",''',
    '''            "Proj",\n            "Base Proj",\n            "Own %",''',
    "disabled columns",
)

# Make the visual meaning explicit without adding another visible column.
app = replace_once(
    app,
    '''            "Proj": (\n                st.column_config.NumberColumn(\n                    "Proj",\n                    format="%.2f",\n                )\n            ),''',
    '''            "Proj": (\n                st.column_config.NumberColumn(\n                    "Proj",\n                    format="%.2f",\n                    help=(\n                        "Projection shown with your manual sentiment adjustment applied. "\n                        "The original source projection is preserved internally and is "\n                        "available under Show research columns as Base Proj."\n                    ),\n                )\n            ),\n\n            "Base Proj": (\n                st.column_config.NumberColumn(\n                    "Base Proj",\n                    format="%.2f",\n                    help="Original source projection before manual sentiment.",\n                )\n            ),''',
    "projection column config",
)

# Value now uses the same displayed projection, so it remains mathematically coherent.
app = app.replace(
    '''                        "Projection points per "\n                        "$1,000 salary."''',
    '''                        "Displayed sentiment-adjusted projection points per "\n                        "$1,000 salary."''',
    1,
)

compile(app, str(APP), "exec")

backup_dir = ROOT / "repair_backup_20261029"
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "app_before_sentiment_projection_v4.py"
if not backup.exists():
    backup.write_text(APP.read_text(encoding="utf-8"), encoding="utf-8")

APP.write_text(app, encoding="utf-8")
print("Applied sentiment projection V4")
print("- Player Pool Proj now visually reflects manual sentiment")
print("- Value updates from the same displayed projection")
print("- original source projection remains preserved as Base Proj in research columns")
print("- optimizer math and canonical player projections were not changed")
