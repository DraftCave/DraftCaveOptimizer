from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def fail(message: str) -> None:
    raise RuntimeError(message)


def find_call_span(lines: list[str], key_marker: str, call_marker: str) -> tuple[int, int]:
    key_idx = next((i for i, line in enumerate(lines) if key_marker in line), None)
    if key_idx is None:
        fail(f"Could not find {key_marker!r} in local app.py")

    start = key_idx
    while start >= 0 and call_marker not in lines[start]:
        start -= 1
    if start < 0:
        fail(f"Could not find call start {call_marker!r} before {key_marker!r}")

    balance = 0
    seen_open = False
    end = start
    for i in range(start, len(lines)):
        # Good enough for these Streamlit widget calls: parentheses in labels are not used here.
        balance += lines[i].count("(") - lines[i].count(")")
        if "(" in lines[i]:
            seen_open = True
        if seen_open and balance <= 0:
            end = i + 1
            break
    else:
        fail(f"Could not find end of {call_marker!r} call")

    # If the call is the sole statement inside a small `with ...:` wrapper,
    # remove that wrapper too so we do not leave an empty block behind.
    call_indent = len(lines[start]) - len(lines[start].lstrip())
    if start > 0:
        prev = start - 1
        while prev >= 0 and not lines[prev].strip():
            prev -= 1
        if prev >= 0:
            prev_indent = len(lines[prev]) - len(lines[prev].lstrip())
            if lines[prev].lstrip().startswith("with ") and lines[prev].rstrip().endswith(":") and prev_indent < call_indent:
                # Only consume the wrapper when nothing else at the call indentation
                # appears before the next sibling block.
                start = prev
    return start, end


original = APP.read_text(encoding="utf-8")
app = original

required = [
    'key="active_position"',
    'key="pool_sort"',
    'height=720',
    'Compact vertical lineup cards',
    'header_controls = st.columns',
]
for marker in required:
    if marker not in app:
        fail(f"Expected local patched UI marker missing: {marker}")

# ---------------------------------------------------------------------------
# 1) Hide visible source diagnostics while preserving validation logic.
# ---------------------------------------------------------------------------
status_start = "# ============================================================\n# SOURCE STATUS\n# ============================================================\n"
status_end = "# ============================================================\n# PRESET\n# ============================================================\n"
if "Data Status · details" in app and status_start in app and status_end in app:
    i = app.index(status_start)
    j = app.index(status_end, i)
    replacement = (
        status_start
        + "\n# Source checks remain active behind the scenes. Only hard failures are shown.\n"
        + "if with_projection == 0:\n"
        + "    st.error(\"No players have resolved projections. Check the slate data files before generating.\")\n"
        + "    st.stop()\n\n\n"
    )
    app = app[:i] + replacement + app[j:]

# ---------------------------------------------------------------------------
# 2) Hide visible Show Research / DVP helper text.
# ---------------------------------------------------------------------------
app, count = re.subn(
    r'(?m)^\s{4}show_research = st\.checkbox\([^\n]*Show research columns[^\n]*\)\n',
    '    show_research = False\n',
    app,
    count=1,
)
if count == 0 and 'show_research = False' not in app:
    fail("Could not hide Show research columns control")

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

# ---------------------------------------------------------------------------
# 3) Move Position buttons directly above Player Pool table.
#    Do NOT touch the existing persistent sort controls.
# ---------------------------------------------------------------------------
lines = app.splitlines(keepends=True)
start, end = find_call_span(lines, 'key="active_position"', 'active_position = st.radio(')
lines[start:end] = []
app = ''.join(lines)

# Filtering still needs a position value before the moved widget renders.
if 'active_position = st.session_state.get("active_position", "ALL")\n    filtered_players = []' not in app:
    needle = '    filtered_players = []\n\n    search_text = (\n'
    if needle not in app:
        fail("Could not locate filtered_players insertion point")
    app = app.replace(
        needle,
        '    active_position = st.session_state.get("active_position", "ALL")\n    filtered_players = []\n\n    search_text = (\n',
        1,
    )

anchor = '    # DS-style compact table controls. The master pool checkbox acts on the\n'
if anchor not in app:
    fail("Could not locate Player Pool header-controls anchor")

position_block = '''    # Position filter sits immediately above the Player Pool table.\n    position_controls = st.columns([6.7, 3.3])\n    with position_controls[0]:\n        active_position = st.radio(\n            "Position",\n            options=["ALL", "QB", "RB", "WR", "TE", "DST"],\n            horizontal=True,\n            key="active_position",\n            label_visibility="collapsed",\n        )\n\n'''
app = app.replace(anchor, position_block + anchor, 1)

# ---------------------------------------------------------------------------
# 4) Nudge Min/Max controls down a little.
# ---------------------------------------------------------------------------
for idx, label in ((2, "Min %"), (3, "Max %")):
    marker = f'''        with header_controls[{idx}]:\n            st.number_input(\n                "{label}",\n'''
    replacement = f'''        with header_controls[{idx}]:\n            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)\n            st.number_input(\n                "{label}",\n'''
    if marker in app and f"ui_v8c_{idx}" not in app:
        app = app.replace(marker, replacement, 1)

# ---------------------------------------------------------------------------
# 5) Clean generated lineup header. The literal &nbsp; text was leaking because
#    Streamlit interpreted the salary dollar sign as math markdown.
# ---------------------------------------------------------------------------
app = app.replace(" &nbsp; · &nbsp; ", "  ·  ")

# Escape dollar signs only in the compact lineup header f-strings.
app = app.replace(
    'f"${lineup.salary:,}  ·  Left **${50_000 - lineup.salary:,}**"',
    'f"Salary **\\${lineup.salary:,}**  ·  Left **\\${50_000 - lineup.salary:,}**"',
)
app = app.replace(
    'f"${lineup.salary:,} · Left **${50_000 - lineup.salary:,}**"',
    'f"Salary **\\${lineup.salary:,}** · Left **\\${50_000 - lineup.salary:,}**"',
)

# Fallback targeted replacement if the salary header still contains unescaped math dollars.
if '&nbsp;' in app:
    app = app.replace('&nbsp;', '')

# ---------------------------------------------------------------------------
# 6) Add ownership diagnostic and partial-generation warning once.
# ---------------------------------------------------------------------------
if 'Ownership constraint:' not in app:
    summary_anchor = '''    reservoir_metrics[4].metric(\n        "Mean Overlap",\n        f"{summary['mean_overlap']:.2f}",\n    )\n\n'''
    if summary_anchor not in app:
        fail("Could not locate generated summary anchor")

    diagnostic = '''    reservoir_metrics[4].metric(\n        "Mean Overlap",\n        f"{summary['mean_overlap']:.2f}",\n    )\n\n    generated_ownerships = [\n        float(lineup.ownership)\n        for lineup in lineups\n        if lineup.ownership is not None\n    ]\n    if generated_settings is not None:\n        own_min_setting = generated_settings.ownership_min\n        own_max_setting = generated_settings.ownership_max\n        if own_min_setting is None and own_max_setting is None:\n            ownership_constraint_label = "OFF"\n        elif own_min_setting is not None and own_max_setting is None:\n            ownership_constraint_label = f"MIN {own_min_setting:.0f}%"\n        elif own_min_setting is None and own_max_setting is not None:\n            ownership_constraint_label = f"MAX {own_max_setting:.0f}%"\n        else:\n            ownership_constraint_label = f"{own_min_setting:.0f}%–{own_max_setting:.0f}%"\n    else:\n        ownership_constraint_label = "Unknown"\n\n    if generated_ownerships:\n        ownership_series = pd.Series(generated_ownerships)\n        st.caption(\n            f"Ownership constraint: {ownership_constraint_label} · "\n            f"Generated min/median/max: {ownership_series.min():.1f}% / "\n            f"{ownership_series.median():.1f}% / {ownership_series.max():.1f}%"\n        )\n    else:\n        st.caption(f"Ownership constraint: {ownership_constraint_label} · Generated ownership unavailable")\n\n    if generated_settings is not None and len(lineups) < int(generated_settings.num_lineups):\n        st.warning(\n            f"Generated {len(lineups)} / {int(generated_settings.num_lineups)} — "\n            "remaining lineups were infeasible under the current constraints."\n        )\n\n'''
    app = app.replace(summary_anchor, diagnostic, 1)

# ---------------------------------------------------------------------------
# Validate before writing.
# ---------------------------------------------------------------------------
compile(app, str(APP), "exec")

# Verification checks must all pass before touching app.py.
checks = {
    "position_filter_moved": app.count('key="active_position"') == 1 and 'position_controls = st.columns' in app,
    "research_helper_hidden": 'show_research = False' in app and 'Show research columns' not in app,
    "dvp_helper_hidden": 'DVP · green' not in app and 'DVP unavailable:' not in app,
    "html_leak_removed": '&nbsp;' not in app,
    "ownership_diagnostic_added": 'Ownership constraint:' in app,
    "source_details_hidden": 'Data Status · details' not in app,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    fail("Verification failed before write: " + ", ".join(failed))

backup_dir = ROOT / "repair_backup_20261029"
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "app_before_ui_cleanup_v8c.py"
if not backup.exists():
    backup.write_text(original, encoding="utf-8")

APP.write_text(app, encoding="utf-8")

print("Applied UI cleanup V8c")
for name, ok in checks.items():
    print(f"VERIFY {name}: {ok}")
print("Optimizer math unchanged")
