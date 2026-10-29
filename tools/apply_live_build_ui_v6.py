from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
THEME = ROOT / "ui_theme.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Could not find {label}; local files may differ from ea721af.")
    return text.replace(old, new, 1)


def remove_between(text: str, start: str, end: str, label: str) -> str:
    if start not in text or end not in text:
        raise RuntimeError(f"Could not find {label} markers.")
    i = text.index(start)
    j = text.index(end, i)
    return text[:i] + text[j:]


app = APP.read_text(encoding="utf-8")
theme = THEME.read_text(encoding="utf-8")

# Require the Work commit checkpoint.
for marker in (
    'from ui_matchups import team_cell_uri, load_dvp, slate_digest, dvp_style, sort_pool',
    'key="pool_sort"',
    'with st.container(key="generate_action")',
):
    if marker not in app:
        raise RuntimeError(f"Expected ea721af checkpoint marker missing: {marker}")

# ---------------------------------------------------------------------------
# 1) Remove Decision / Intervention Log from the live UI.
# ---------------------------------------------------------------------------
log_start = '''        with st.expander(\n            "Decision / Intervention Log",\n            expanded=False,\n        ):\n'''
log_end = '''\n\n# ============================================================\n# PLAYER DATA\n# ============================================================\n'''
app = remove_between(app, log_start, log_end, "Decision / Intervention Log")

# ---------------------------------------------------------------------------
# 2) Collapse low-frequency Player Pool filters and put position + persistent
#    sort immediately above the table.
# ---------------------------------------------------------------------------
old_position = '''    active_position = st.radio(\n        "Position",\n        options=[\n            "ALL",\n            "QB",\n            "RB",\n            "WR",\n            "TE",\n            "DST",\n        ],\n        horizontal=True,\n        key="active_position",\n        label_visibility="collapsed",\n    )\n'''
new_position = '''    # Position selector is rendered directly above the table below.\n    # Read its persisted value here so filters can use it before the widget renders.\n    active_position = st.session_state.get("active_position", "ALL")\n'''
app = replace_once(app, old_position, new_position, "Player Pool position selector")

# Wrap the existing quick filters in a collapsed expander to give the player
# table substantially more vertical prominence during live builds.
filters_start = '''    # --------------------------------------------------------\n    # QUICK FILTERS\n    # --------------------------------------------------------\n\n'''
filters_end = '''\n\n    # --------------------------------------------------------\n    # FILTER PLAYER LIST\n    # --------------------------------------------------------\n'''
if filters_start not in app or filters_end not in app:
    raise RuntimeError("Could not find Quick Filters section")
i = app.index(filters_start) + len(filters_start)
j = app.index(filters_end, i)
filter_body = app[i:j]
indented_filter_body = "".join(
    ("    " + line if line.strip() else line)
    for line in filter_body.splitlines(keepends=True)
)
app = (
    app[:i]
    + '    with st.expander("Filters", expanded=False):\n'
    + indented_filter_body
    + app[j:]
)

old_sort = '''    sort_left, sort_right = st.columns([3, 2])\n    with sort_left:\n        pool_sort = st.selectbox("Sort", ["Salary", "Own %", "Proj", "Base Proj", "Ceiling", "Value", "Player", "DVP", "Min %", "Max %"], key="pool_sort")\n    with sort_right:\n        pool_sort_direction = st.radio("Order", ["High to low", "Low to high"], horizontal=True, key="pool_sort_direction")\n    st.caption("Sort controls persist through edits and generation. Table-header sorting is temporary.")\n'''
new_sort = '''    # Keep the two controls used most often during live builds attached to the table.\n    pool_nav = st.columns([5.6, 2.2, 2.2])\n    with pool_nav[0]:\n        active_position = st.radio(\n            "Position",\n            options=["ALL", "QB", "RB", "WR", "TE", "DST"],\n            horizontal=True,\n            key="active_position",\n            label_visibility="collapsed",\n        )\n    with pool_nav[1]:\n        pool_sort = st.selectbox(\n            "Persistent Sort",\n            ["Salary", "Own %", "Proj", "Base Proj", "Ceiling", "Value", "Player", "DVP", "Min %", "Max %"],\n            key="pool_sort",\n        )\n    with pool_nav[2]:\n        pool_sort_direction = st.selectbox(\n            "Order",\n            ["↓ High to low", "↑ Low to high"],\n            key="pool_sort_direction_v6",\n        )\n'''
app = replace_once(app, old_sort, new_sort, "persistent sort controls")
app = replace_once(
    app,
    'pool_df = sort_pool(pool_df, pool_sort, pool_sort_direction == "High to low")',
    'pool_df = sort_pool(pool_df, pool_sort, pool_sort_direction.startswith("↓"))',
    "persistent sort application",
)

# Make the Player Pool the dominant working surface.
app = replace_once(app, '        height=455,', '        height=720,', "Player Pool height")

# ---------------------------------------------------------------------------
# 3) Generate / Regenerate: compact, centered, normal-flow button. No floating
#    overlay and no full-width banner.
# ---------------------------------------------------------------------------
old_generate = '''with st.container(key="generate_action"):\n\n    generate_clicked = st.button(\n        f"{'REGENERATE' if 'generation_result' in st.session_state else 'GENERATE'} {settings.num_lineups} LINEUPS",\n        key="generate_lineups",\n        type="primary",\n        width="stretch",\n    )\n\n    clear_results_clicked = st.button(\n        "Clear Generated Results",\n        width="stretch",\n    )\n'''
new_generate = '''with st.container(key="generate_action"):\n    generate_cols = st.columns([3.4, 1.8, 1.4, 3.4])\n    with generate_cols[1]:\n        generate_clicked = st.button(\n            f"{'Regenerate' if 'generation_result' in st.session_state else 'Generate'} {settings.num_lineups} Lineups",\n            key="generate_lineups",\n            type="primary",\n            width="stretch",\n        )\n    with generate_cols[2]:\n        clear_results_clicked = st.button(\n            "Clear",\n            width="stretch",\n            help="Clear the current generated reservoir.",\n        )\n    st.caption(\n        f"{settings.num_lineups} lineups · {settings.minimum_uniques} uniques · "\n        f"{int(round(settings.randomization_pct * 100))}% randomization"\n    )\n'''
app = replace_once(app, old_generate, new_generate, "Generate action block")

# ---------------------------------------------------------------------------
# 4) Generated Lineups: ALL view becomes a vertical lineup-card browser. The
#    existing position exposure/usage view remains available for QB/RB/WR/TE/DST.
# ---------------------------------------------------------------------------
app = replace_once(
    app,
    '''            "Portfolio Review",\n            "Stacks & Games",\n            "Portfolio Risk",\n            "Repetition",\n            "Export",\n''',
    '''            "Lineups",\n            "Stacks & Games",\n            "Portfolio Risk",\n            "Repetition",\n            "Export",\n''',
    "generated tab labels",
)

start = '''    with tabs[0]:\n\n        review_position = st.radio(\n'''
end = '''\n\n    # --------------------------------------------------------\n    # STACK ANALYSIS\n    # --------------------------------------------------------\n'''
if start not in app or end not in app:
    raise RuntimeError("Could not find generated Lineups tab block")
i = app.index(start)
j = app.index(end, i)
new_lineups = '''    with tabs[0]:\n\n        review_position = st.radio(\n            "Generated lineup review",\n            options=["ALL", "QB", "RB", "WR", "TE", "DST"],\n            horizontal=True,\n            key="generated_portfolio_review_position",\n            label_visibility="collapsed",\n        )\n\n        if review_position == "ALL":\n            lineup_controls = st.columns([2.2, 1.6, 5.2])\n            with lineup_controls[0]:\n                lineup_sort = st.selectbox(\n                    "Sort Lineups",\n                    ["Projection", "Ceiling", "Ownership", "Salary", "Salary Left", "Lineup #"],\n                    key="generated_lineup_sort_v6",\n                )\n            with lineup_controls[1]:\n                lineup_sort_desc = st.selectbox(\n                    "Order",\n                    ["↓ High to low", "↑ Low to high"],\n                    key="generated_lineup_sort_direction_v6",\n                )\n\n            indexed_lineups = list(enumerate(lineups, start=1))\n            sort_keys = {\n                "Projection": lambda item: item[1].projection,\n                "Ceiling": lambda item: item[1].ceiling,\n                "Ownership": lambda item: item[1].ownership,\n                "Salary": lambda item: item[1].salary,\n                "Salary Left": lambda item: 50_000 - item[1].salary,\n                "Lineup #": lambda item: item[0],\n            }\n            indexed_lineups.sort(\n                key=lambda item: (sort_keys[lineup_sort](item) if sort_keys[lineup_sort](item) is not None else float("-inf")),\n                reverse=lineup_sort_desc.startswith("↓"),\n            )\n\n            st.caption(\n                "Each lineup is shown as a vertical card. Projection, ceiling, ownership, salary and salary left are visible before the roster."\n            )\n\n            slot_order = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "DST"]\n            for original_number, lineup in indexed_lineups:\n                with st.container(border=True):\n                    header = st.columns([1.15, 1, 1, 1, 1, 1])\n                    header[0].markdown(f"**Lineup {original_number}**")\n                    header[1].metric("Proj", f"{lineup.projection:.2f}")\n                    header[2].metric("Ceiling", "—" if lineup.ceiling is None else f"{lineup.ceiling:.2f}")\n                    header[3].metric("Own", "—" if lineup.ownership is None else f"{lineup.ownership:.1f}%")\n                    header[4].metric("Salary", f"${lineup.salary:,}")\n                    header[5].metric("Left", f"${50_000 - lineup.salary:,}")\n\n                    roster_rows = []\n                    for slot in slot_order:\n                        player = lineup.slots.get(slot)\n                        if player is None:\n                            continue\n                        roster_rows.append(\n                            {\n                                "Slot": slot,\n                                "Player": player.name,\n                                "Team": player.team,\n                                "Opp": player.opponent,\n                                "Salary": player.salary,\n                                "Proj": player.projection,\n                                "Own %": player.ownership,\n                            }\n                        )\n                    show_table(\n                        pd.DataFrame(roster_rows),\n                        width="stretch",\n                        hide_index=True,\n                    )\n                    st.caption(f"Stack story · {lineup.story_signature()}")\n\n        else:\n            review_exposure = player_exposure(lineups).copy()\n            review_exposure = review_exposure.loc[\n                review_exposure["Position"] == review_position\n            ].copy()\n\n            control_lookup = {\n                (player.name, player.position, player.team): st.session_state.player_controls.get(int(player.dk_id), {})\n                for player in available\n            }\n            review_exposure["Min %"] = [\n                int(control_lookup.get((row.Name, row.Position, row.Team), {}).get("Min %", 0))\n                for row in review_exposure.itertuples(index=False)\n            ]\n            review_exposure["Max %"] = [\n                int(control_lookup.get((row.Name, row.Position, row.Team), {}).get("Max %", 100))\n                for row in review_exposure.itertuples(index=False)\n            ]\n\n            review_left, review_right = st.columns([1.0, 2.25])\n            with review_left:\n                st.markdown(f"### {review_position} Exposure")\n                show_table(\n                    review_exposure[["Name", "Team", "Position", "Count", "Exposure", "Min %", "Max %"]],\n                    width="stretch",\n                    height=620,\n                )\n            with review_right:\n                st.markdown(f"### {review_position} Usage · {len(lineups)} generated")\n                show_table(\n                    position_lineup_table(lineups, review_position),\n                    width="stretch",\n                    height=620,\n                )\n'''
app = app[:i] + new_lineups + app[j:]

# ---------------------------------------------------------------------------
# 5) CSS: remove floating generate overlay and excess bottom padding.
# ---------------------------------------------------------------------------
theme = replace_once(
    theme,
    '        padding-bottom: 11rem;',
    '        padding-bottom: 4rem;',
    "main bottom padding",
)
css_start = '''    .st-key-generate_action {\n        position: fixed; bottom: 0.5rem; right: 1rem; z-index: 100;\n        width: min(340px, calc(100vw - 2rem)); padding: 0.6rem;\n        background: var(--dc-panel); border: 1px solid var(--dc-border);\n        border-radius: 10px; box-shadow: 0 4px 24px #0008;\n    }\n'''
theme = replace_once(
    theme,
    css_start,
    '''    .st-key-generate_action {\n        margin-top: 0.35rem;\n        margin-bottom: 0.6rem;\n    }\n''',
    "floating Generate CSS",
)

# Compile before writing. No optimizer/config/model code is touched.
compile(app, str(APP), "exec")
compile(theme, str(THEME), "exec")

backup_dir = ROOT / "repair_backup_20261029"
backup_dir.mkdir(parents=True, exist_ok=True)
(APP.parent / "repair_backup_20261029" / "app_before_live_build_ui_v6.py").write_text(
    APP.read_text(encoding="utf-8"), encoding="utf-8"
)
(APP.parent / "repair_backup_20261029" / "ui_theme_before_live_build_ui_v6.py").write_text(
    THEME.read_text(encoding="utf-8"), encoding="utf-8"
)

APP.write_text(app, encoding="utf-8")
THEME.write_text(theme, encoding="utf-8")

print("Applied live-build UI V6")
print("- removed Decision / Intervention Log")
print("- collapsed low-use Player Pool filters")
print("- moved position + persistent sort directly above the Player Pool table")
print("- expanded Player Pool height")
print("- Generate/Regenerate is compact, centered, and no longer floating")
print("- generated ALL view now uses vertical lineup cards with Proj/Ceiling/Own/Salary/Left")
print("- position exposure/usage review remains available")
print("- optimizer math unchanged")
