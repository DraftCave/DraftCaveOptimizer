from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise RuntimeError(f"Could not find {label}: {needle!r}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Could not find {label}; local app.py differs from expected patched layout.")
    return text.replace(old, new, 1)


original = APP.read_text(encoding="utf-8")
app = original

for marker in (
    'with st.container(border=True):',
    '👥 Player Pool',
    'key="active_position"',
    'height=720',
    'Compact vertical lineup cards',
):
    require(app, marker, "local patched UI marker")

# 1) Hide source/data diagnostics from the normal build surface.
status_start = "# ============================================================\n# SOURCE STATUS\n# ============================================================\n"
status_end = "# ============================================================\n# PRESET\n# ============================================================\n"
if status_start in app and status_end in app:
    i = app.index(status_start)
    j = app.index(status_end, i)
    app = (
        app[:i]
        + status_start
        + "\n# Source validation remains active behind the scenes.\n"
        + "if with_projection == 0:\n"
        + "    st.error(\"No players have resolved projections. Check the slate data files before generating.\")\n"
        + "    st.stop()\n\n\n"
        + app[j:]
    )

# 2) Remove visible research/DVP helper clutter while preserving backing data.
research_pattern = re.compile(
    r'(?m)^\s{4}show_research = st\.checkbox\("Show research columns"[^\n]*\)\n'
    r'(?:\s*\n)?'
    r'\s{4}st\.caption\("DVP · green 1–8 · yellow 9–16 · orange 17–24 · red 25–32 · 1 = easiest\. Visual only\. Missing = —\."\)\n'
    r'\s{4}if not dvp_values:\n'
    r'\s{8}st\.caption\(dvp_status\)\n'
)
if research_pattern.search(app):
    app = research_pattern.sub('    show_research = False\n', app, count=1)
else:
    app = re.sub(
        r'(?m)^\s{4}show_research = st\.checkbox\([^\n]*Show research columns[^\n]*\)\n',
        '    show_research = False\n',
        app,
        count=1,
    )
    app = re.sub(
        r'(?m)^\s{4}st\.caption\("DVP · green[^\n]*\n',
        '',
        app,
        count=1,
    )
    app = re.sub(
        r'(?m)^\s{4}if not dvp_values:\n\s{8}st\.caption\(dvp_status\)\n',
        '',
        app,
        count=1,
    )

# 3) Rebuild persistent-sort area without Position; render Position above table.
if 'active_position = st.session_state.get("active_position", "ALL")\n    filtered_players = []' not in app:
    app = replace_once(
        app,
        '    filtered_players = []\n\n    search_text = (\n',
        '    active_position = st.session_state.get("active_position", "ALL")\n    filtered_players = []\n\n    search_text = (\n',
        "persisted active position before filtering",
    )

v7_nav_pattern = re.compile(
    r'\s{4}# Canonical persistent sort\.[\s\S]*?'
    r'\s{4}st\.caption\("Persistent sort stays active after player-pool edits\. Use this row instead of clicking a table header when you want the order preserved\."\)\n',
)
v6_nav_pattern = re.compile(
    r'\s{4}# Keep the two controls used most often during live builds attached to the table\.[\s\S]*?'
    r'\s{4}st\.caption\("Sort controls persist through edits and generation\. Table-header sorting is temporary\."\)\n',
)

sort_only = '''    # Persistent Player Pool sort. Position is rendered directly above the table.\n    sort_nav = st.columns([8.6, 1.4])\n    with sort_nav[0]:\n        pool_sort = st.radio(\n            "Sort by",\n            ["Salary", "Own %", "Proj", "Ceiling", "Value", "Player", "DVP"],\n            horizontal=True,\n            key="pool_sort",\n            label_visibility="collapsed",\n        )\n    with sort_nav[1]:\n        pool_sort_direction = st.selectbox(\n            "Order",\n            ["↓", "↑"],\n            key="pool_sort_direction_v8b",\n            label_visibility="collapsed",\n        )\n    st.caption("Persistent sort stays active after Player Pool edits.")\n'''

if v7_nav_pattern.search(app):
    app = v7_nav_pattern.sub(sort_only, app, count=1)
elif v6_nav_pattern.search(app):
    app = v6_nav_pattern.sub(sort_only, app, count=1)
else:
    generic_nav = re.compile(
        r'\s{4}pool_nav = st\.columns\([^\n]*\)[\s\S]*?'
        r'\s{4}st\.caption\([^\n]*Persistent sort[^\n]*\)\n',
        re.IGNORECASE,
    )
    if generic_nav.search(app):
        app = generic_nav.sub(sort_only, app, count=1)
    else:
        raise RuntimeError("Could not locate the current Player Pool sort/navigation block.")

app = app.replace(
    'pool_df = sort_pool(pool_df, pool_sort, pool_sort_direction.startswith("↓"))',
    'pool_df = sort_pool(pool_df, pool_sort, pool_sort_direction == "↓")',
)
app = app.replace(
    'pool_df = sort_pool(pool_df, pool_sort, pool_sort_direction == "High to low")',
    'pool_df = sort_pool(pool_df, pool_sort, pool_sort_direction == "↓")',
)

prior_position_row = re.compile(
    r'\s{4}position_row = st\.columns\([^\n]*\)\n'
    r'\s{4}with position_row\[0\]:\n'
    r'\s{8}active_position = st\.radio\([\s\S]*?\n\s{12}label_visibility="collapsed",\n\s{8}\)\n',
)
app = prior_position_row.sub('', app, count=1)

header_anchor = '    # DS-style compact table controls. The master pool checkbox acts on the\n'
require(app, header_anchor, "Player Pool table-control anchor")
position_block = '''    # Position filter sits immediately above the Player Pool table.\n    position_controls = st.columns([6.7, 3.3])\n    with position_controls[0]:\n        active_position = st.radio(\n            "Position",\n            options=["ALL", "QB", "RB", "WR", "TE", "DST"],\n            horizontal=True,\n            key="active_position",\n            label_visibility="collapsed",\n        )\n\n'''
app = replace_once(app, header_anchor, position_block + header_anchor, "position filter placement")

# 4) Nudge bulk Min/Max controls down slightly.
for idx, label in ((2, "Min %"), (3, "Max %")):
    needle = f'''        with header_controls[{idx}]:\n            st.number_input(\n                "{label}",\n'''
    replacement = f'''        with header_controls[{idx}]:\n            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)\n            st.number_input(\n                "{label}",\n'''
    if needle in app:
        app = app.replace(needle, replacement, 1)

# 5) Clean generated lineup header: no &nbsp; / markdown leakage.
card_header_pattern = re.compile(
    r'\s{28}st\.markdown\(\n'
    r'\s{32}f"\*\*L\{original_number\}\*\*[\s\S]*?'
    r'\s{28}\)\n',
)
clean_header = '''                            st.markdown(\n                                f"**L{original_number}**  ·  "\n                                f"Proj **{lineup.projection:.1f}**  ·  "\n                                f"Ceil **{ceiling_text}**  ·  "\n                                f"Own **{own_text}**  ·  "\n                                f"Salary **\\${lineup.salary:,}**  ·  "\n                                f"Left **\\${50_000 - lineup.salary:,}**"\n                            )\n'''
if card_header_pattern.search(app):
    app = card_header_pattern.sub(clean_header, app, count=1)
else:
    raise RuntimeError("Could not locate generated lineup-card header for cleanup.")

# 6) Add generated ownership diagnostic and partial-generation warning once.
if "Ownership constraint:" not in app:
    summary_anchor = '''    reservoir_metrics[4].metric(\n        "Mean Overlap",\n        f"{summary['mean_overlap']:.2f}",\n    )\n\n'''
    require(app, summary_anchor, "generated summary anchor")
    diag = '''    reservoir_metrics[4].metric(\n        "Mean Overlap",\n        f"{summary['mean_overlap']:.2f}",\n    )\n\n    generated_ownerships = [\n        float(lineup.ownership)\n        for lineup in lineups\n        if lineup.ownership is not None\n    ]\n    if generated_settings is not None:\n        own_min_setting = generated_settings.ownership_min\n        own_max_setting = generated_settings.ownership_max\n        if own_min_setting is None and own_max_setting is None:\n            ownership_constraint_label = "OFF"\n        elif own_min_setting is not None and own_max_setting is None:\n            ownership_constraint_label = f"MIN {own_min_setting:.0f}%"\n        elif own_min_setting is None and own_max_setting is not None:\n            ownership_constraint_label = f"MAX {own_max_setting:.0f}%"\n        else:\n            ownership_constraint_label = f"{own_min_setting:.0f}%–{own_max_setting:.0f}%"\n    else:\n        ownership_constraint_label = "Unknown"\n\n    if generated_ownerships:\n        ownership_series = pd.Series(generated_ownerships)\n        st.caption(\n            f"Ownership constraint: {ownership_constraint_label} · "\n            f"Generated min/median/max: {ownership_series.min():.1f}% / "\n            f"{ownership_series.median():.1f}% / {ownership_series.max():.1f}%"\n        )\n    else:\n        st.caption(f"Ownership constraint: {ownership_constraint_label} · Generated ownership unavailable")\n\n    if generated_settings is not None and len(lineups) < int(generated_settings.num_lineups):\n        st.warning(\n            f"Generated {len(lineups)} / {int(generated_settings.num_lineups)} — "\n            "remaining lineups were infeasible under the current constraints."\n        )\n\n'''
    app = replace_once(app, summary_anchor, diag, "generated ownership diagnostic")

compile(app, str(APP), "exec")

backup_dir = ROOT / "repair_backup_20261029"
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "app_before_ui_cleanup_v8b.py"
if not backup.exists():
    backup.write_text(original, encoding="utf-8")

APP.write_text(app, encoding="utf-8")

print("Applied UI cleanup V8b")
print("VERIFY position filter moved:", "position_controls = st.columns" in app)
print("VERIFY research/DVP helper hidden:", 'show_research = False' in app)
print("VERIFY lineup HTML leak removed:", '&nbsp;' not in app)
print("VERIFY ownership diagnostic added:", 'Ownership constraint:' in app)
print("VERIFY source-status live block hidden:", 'Data Status · details' not in app)
print("Optimizer math unchanged")
