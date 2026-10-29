from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
THEME = ROOT / "ui_theme.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Could not find {label}; local files may differ from expected checkpoint.")
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8")
theme = THEME.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# 1) Remove the V2 Quick Sentiment selector + horizontal pill strip entirely.
#    Keep sentiment editing inside the player table until a true inline popover
#    is implemented with a dedicated component.
# ---------------------------------------------------------------------------
start = '''    # DS-style Quick Sentiment: choose a player once, then use one-click horizontal pills.\n'''
end = '''    show_research = st.checkbox("Show research columns", value=False, key="show_research_columns_v5")\n'''
if start in app:
    i = app.index(start)
    j = app.index(end, i)
    app = app[:i] + end + app[j + len(end):]

# Restore the row-level sentiment editor (no separate selector/bar).
app = app.replace(
    '''            "Visual", "DVP", "Sentiment",\n            "ID",''',
    '''            "Visual", "DVP",\n            "ID",''',
    1,
)
app = app.replace(
    '''            "Sentiment": st.column_config.TextColumn(\n                "Sentiment",\n                width="small",\n                help="Current objective-only sentiment. Use Quick Sentiment above for one-click changes.",\n            ),''',
    '''            "Sentiment": st.column_config.SelectboxColumn(\n                "Sentiment",\n                options=[sentiment_display(state) for state in PLAYER_SENTIMENT_OPTIONS],\n                required=True,\n                width="small",\n                help="Objective-only sentiment adjustment; displayed projection remains unchanged.",\n            ),''',
    1,
)

# ---------------------------------------------------------------------------
# 2) Ownership must remain numeric. Text sorting caused values like 9.3 to sort
#    ahead of 14.4, making players appear to disappear when sorting.
# ---------------------------------------------------------------------------
app = replace_once(
    app,
    '''                "Own %": "—" if p.ownership is None else f"{p.ownership:.1f}",''',
    '''                "Own %": None if p.ownership is None else float(p.ownership),''',
    "numeric ownership row value",
)
app = replace_once(
    app,
    '''            "Own %": st.column_config.TextColumn("Own %", width="small"),''',
    '''            "Own %": st.column_config.NumberColumn(\n                "Own %",\n                format="%.1f",\n                width="small",\n                help="Projected ownership; numeric sorting is preserved.",\n            ),''',
    "numeric ownership column config",
)

# ---------------------------------------------------------------------------
# 3) Compact the visibly wasteful columns.
# ---------------------------------------------------------------------------
app = app.replace(
    '''            "Player": st.column_config.TextColumn("Player", width="medium"),''',
    '''            "Player": st.column_config.TextColumn("Player", width="medium"),''',
    1,
)
app = app.replace(
    '''                    format="%d%%",\n                )\n            ),\n\n            "Max %": (''',
    '''                    format="%d%%",\n                    width="small",\n                )\n            ),\n\n            "Max %": (''',
    1,
)
app = app.replace(
    '''                    step=5,\n                    format="%d%%",\n                )\n            ),\n\n            "ID": (''',
    '''                    step=5,\n                    format="%d%%",\n                    width="small",\n                )\n            ),\n\n            "ID": (''',
    1,
)

# ui_theme identity guard was forcing Player to large, creating the big empty gap.
theme = replace_once(
    theme,
    '''            column_config["Player"] = st.column_config.TextColumn(\n                "Player",\n                width="large",\n                help="Player name — always visible in the default pool view.",\n            )''',
    '''            column_config["Player"] = st.column_config.TextColumn(\n                "Player",\n                width="medium",\n                help="Player name — always visible in the default pool view.",\n            )''',
    "Player identity-guard width",
)

# Compile before writing so a failed transform never breaks the local app.
compile(app, str(APP), "exec")
compile(theme, str(THEME), "exec")

backup_dir = ROOT / "repair_backup_20261029"
backup_dir.mkdir(parents=True, exist_ok=True)
(APP.parent / "repair_backup_20261029" / "app_before_player_pool_cleanup_v3.py").write_text(
    APP.read_text(encoding="utf-8"), encoding="utf-8"
)
(APP.parent / "repair_backup_20261029" / "ui_theme_before_player_pool_cleanup_v3.py").write_text(
    THEME.read_text(encoding="utf-8"), encoding="utf-8"
)

APP.write_text(app, encoding="utf-8")
THEME.write_text(theme, encoding="utf-8")
print("Applied Player Pool cleanup V3")
print("- removed separate Quick Sentiment selector/bar")
print("- ownership is numeric, so sorting is numerically correct")
print("- compacted Player / Min % / Max % columns")
