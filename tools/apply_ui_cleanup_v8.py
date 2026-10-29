from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Could not find {label}; local app.py may differ from the V7 checkpoint.")
    return text.replace(old, new, 1)


def remove_between(text: str, start: str, end: str, label: str) -> str:
    if start not in text or end not in text:
        raise RuntimeError(f"Could not find {label} markers.")
    i = text.index(start)
    j = text.index(end, i)
    return text[:i] + text[j:]


app = APP.read_text(encoding="utf-8")

for marker in (
    'key="pool_sort_direction_v7"',
    'Compact vertical lineup cards · two per row',
    'key="generated_lineup_sort_v6"',
):
    if marker not in app:
        raise RuntimeError(f"Expected V7 marker missing: {marker}")

# ---------------------------------------------------------------------------
# 1) Hide source/data-status diagnostics from the normal live-build surface.
#    Data validation logic remains intact; only presentation is removed.
# ---------------------------------------------------------------------------
status_start = '''# ============================================================\n# SOURCE STATUS\n# ============================================================\n\n'''
status_end = '''\n\n# ============================================================\n# PRESET\n# ============================================================\n'''
if status_start not in app or status_end not in app:
    raise RuntimeError("Could not find Source Status block")
i = app.index(status_start)
j = app.index(status_end, i)
replacement = '''# ============================================================\n# SOURCE STATUS\n# ============================================================\n\n# Source checks remain active behind the scenes. Keep only hard failures\n# visible in the live-build UI.\nif with_projection == 0:\n    st.error("No players have resolved projections. Check the slate data files before generating.")\n    st.stop()\n\n'''
app = app[:i] + replacement + app[j:]

# ---------------------------------------------------------------------------
# 2) Keep sort controls up top, move Position to the table control row.
# ---------------------------------------------------------------------------
old_nav = '''    # Canonical persistent sort. Clicking a Streamlit table header is temporary;\n    # these controls survive checkbox/sentiment/exposure edits and reruns.\n    pool_nav = st.columns([4.9, 3.8, 1.3])\n    with pool_nav[0]:\n        active_position = st.radio(\n            "Position",\n            options=["ALL", "QB", "RB", "WR", "TE", "DST"],\n            horizontal=True,\n            key="active_position",\n            label_visibility="collapsed",\n        )\n    with pool_nav[1]:\n        pool_sort = st.radio(\n            "Sort by",\n            ["Salary", "Own %", "Proj", "Ceiling", "Value", "Player", "DVP"],\n            horizontal=True,\n            key="pool_sort",\n            label_visibility="collapsed",\n        )\n    with pool_nav[2]:\n        pool_sort_direction = st.selectbox(\n            "Order",\n            ["↓", "↑"],\n            key="pool_sort_direction_v7",\n            label_visibility="collapsed",\n        )\n    st.caption("Persistent sort stays active after player-pool edits. Use this row instead of clicking a table header when you want the order preserved.")\n'''
new_nav = '''    # Canonical persistent sort. Position is rendered later, directly above\n    # the Player Pool table where it is used.\n    sort_nav = st.columns([7.9, 1.1])\n    with sort_nav[0]:\n        pool_sort = st.radio(\n            "Sort by",\n            ["Salary", "Own %", "Proj", "Ceiling", "Value", "Player", "DVP"],\n            horizontal=True,\n            key="pool_sort",\n            label_visibility="collapsed",\n        )\n    with sort_nav[1]:\n        pool_sort_direction = st.selectbox(\n            "Order",\n            ["↓", "↑"],\n            key="pool_sort_direction_v7",\n            label_visibility="collapsed",\n        )\n    st.caption("Persistent sort stays active after Player Pool edits.")\n'''
app = replace_once(app, old_nav, new_nav, "V7 Player Pool nav")

old_filtered = '''    filtered_players = []\n\n    search_text = (\n'''
new_filtered = '''    active_position = st.session_state.get("active_position", "ALL")\n    filtered_players = []\n\n    search_text = (\n'''
app = replace_once(app, old_filtered, new_filtered, "filtered players intro")

# Insert the Position selector immediately before Advanced player controls,
# which places it directly above the table-control/exposure row.
anchor = '''    # Preserve existing explicit locks; keep infrequently used controls collapsed.\n'''
position_block = '''    position_row = st.columns([5.0, 5.0])\n    with position_row[0]:\n        active_position = st.radio(\n            "Position",\n            options=["ALL", "QB", "RB", "WR", "TE", "DST"],\n            horizontal=True,\n            key="active_position",\n            label_visibility="collapsed",\n        )\n\n'''
app = replace_once(app, anchor, position_block + anchor, "Advanced controls anchor")

# Move Min/Max slightly down and keep them aligned to the right.
old_header_start = '''    header_controls = st.columns([0.85, 7.15, 1.0, 1.0])\n\n    select_all_key = f"in_pool_all_{active_position}"\n'''
new_header_start = '''    header_controls = st.columns([0.85, 7.0, 1.075, 1.075])\n\n    select_all_key = f"in_pool_all_{active_position}"\n'''
app = replace_once(app, old_header_start, new_header_start, "header control widths")

# Add a tiny spacer above the two bulk exposure controls.
app = replace_once(
    app,
    '''        with header_controls[2]:\n            st.number_input(\n                "Min %",\n''',
    '''        with header_controls[2]:\n            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)\n            st.number_input(\n                "Min %",\n''',
    "bulk Min spacer",
)
app = replace_once(
    app,
    '''        with header_controls[3]:\n            st.number_input(\n                "Max %",\n''',
    '''        with header_controls[3]:\n            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)\n            st.number_input(\n                "Max %",\n''',
    "bulk Max spacer",
)

# ---------------------------------------------------------------------------
# 3) Fix lineup-card header markdown/HTML leakage. Use plain markdown text and
#    escape currency symbols so Streamlit cannot treat them as math syntax.
# ---------------------------------------------------------------------------
old_card_header = '''                            st.markdown(\n                                f"**L{original_number}** &nbsp; · &nbsp; "\n                                f"Proj **{lineup.projection:.1f}** &nbsp; · &nbsp; "\n                                f"Ceil **{ceiling_text}** &nbsp; · &nbsp; "\n                                f"Own **{own_text}** &nbsp; · &nbsp; "\n                                f"${lineup.salary:,} &nbsp; · &nbsp; Left **${50_000 - lineup.salary:,}**"\n                            )\n'''
new_card_header = '''                            st.markdown(\n                                f"**L{original_number}**  ·  "\n                                f"Proj **{lineup.projection:.1f}**  ·  "\n                                f"Ceil **{ceiling_text}**  ·  "\n                                f"Own **{own_text}**  ·  "\n                                f"Salary **\\${lineup.salary:,}**  ·  "\n                                f"Left **\\${50_000 - lineup.salary:,}**"\n                            )\n'''
app = replace_once(app, old_card_header, new_card_header, "lineup card header")

# ---------------------------------------------------------------------------
# 4) Generated-build ownership diagnostic + partial-generation warning.
# ---------------------------------------------------------------------------
summary_anchor = '''    reservoir_metrics[4].metric(\n        "Mean Overlap",\n        f"{summary['mean_overlap']:.2f}",\n    )\n\n\n    tabs = st.tabs(\n'''
ownership_diag = '''    reservoir_metrics[4].metric(\n        "Mean Overlap",\n        f"{summary['mean_overlap']:.2f}",\n    )\n\n    generated_ownerships = [\n        float(lineup.ownership)\n        for lineup in lineups\n        if lineup.ownership is not None\n    ]\n    if generated_settings is not None:\n        own_min_setting = generated_settings.ownership_min\n        own_max_setting = generated_settings.ownership_max\n        if own_min_setting is None and own_max_setting is None:\n            ownership_constraint_label = "OFF"\n        elif own_min_setting is not None and own_max_setting is None:\n            ownership_constraint_label = f"MIN {own_min_setting:.0f}%"\n        elif own_min_setting is None and own_max_setting is not None:\n            ownership_constraint_label = f"MAX {own_max_setting:.0f}%"\n        else:\n            ownership_constraint_label = f"{own_min_setting:.0f}%–{own_max_setting:.0f}%"\n    else:\n        ownership_constraint_label = "Unknown"\n\n    if generated_ownerships:\n        ownership_series = pd.Series(generated_ownerships)\n        st.caption(\n            f"Ownership constraint: {ownership_constraint_label} · "\n            f"Generated min/median/max: {ownership_series.min():.1f}% / "\n            f"{ownership_series.median():.1f}% / {ownership_series.max():.1f}%"\n        )\n    else:\n        st.caption(f"Ownership constraint: {ownership_constraint_label} · Generated ownership unavailable")\n\n    if generated_settings is not None and len(lineups) < int(generated_settings.num_lineups):\n        st.warning(\n            f"Generated {len(lineups)} / {int(generated_settings.num_lineups)} — "\n            "remaining lineups were infeasible under the current constraints."\n        )\n\n\n    tabs = st.tabs(\n'''
app = replace_once(app, summary_anchor, ownership_diag, "generated ownership diagnostic")

compile(app, str(APP), "exec")

backup_dir = ROOT / "repair_backup_20261029"
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "app_before_ui_cleanup_v8.py"
if not backup.exists():
    backup.write_text(APP.read_text(encoding="utf-8"), encoding="utf-8")

APP.write_text(app, encoding="utf-8")
print("Applied UI cleanup V8")
print("- hidden Data Status/source diagnostics from normal live-build view")
print("- moved position filter directly above Player Pool table")
print("- nudged bulk Min/Max controls down for alignment")
print("- fixed lineup-card HTML/markdown leakage")
print("- added ownership constraint + min/median/max diagnostic")
print("- added partial-generation infeasibility warning")
print("- optimizer math unchanged")
