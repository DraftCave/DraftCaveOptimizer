from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def fail(message: str) -> None:
    raise RuntimeError(message)


def find_call_span(lines: list[str], text_marker: str, call_marker: str) -> tuple[int, int]:
    marker_idx = next((i for i, line in enumerate(lines) if text_marker in line), None)
    if marker_idx is None:
        fail(f"Could not find {text_marker!r} in local app.py")

    start = marker_idx
    while start >= 0 and call_marker not in lines[start]:
        start -= 1
    if start < 0:
        fail(f"Could not find {call_marker!r} before {text_marker!r}")

    balance = 0
    seen_open = False
    for i in range(start, len(lines)):
        balance += lines[i].count("(") - lines[i].count(")")
        if "(" in lines[i]:
            seen_open = True
        if seen_open and balance <= 0:
            return start, i + 1

    fail(f"Could not find end of {call_marker!r}")


original = APP.read_text(encoding="utf-8")
app = original

for marker in (
    'key="active_position"',
    'key="pool_sort"',
    'height=720',
    'Compact vertical lineup cards',
    'header_controls = st.columns',
):
    if marker not in app:
        fail(f"Expected patched UI marker missing: {marker}")

# ---------------------------------------------------------------------------
# 1) Hide visible source diagnostics, preserving validation.
# ---------------------------------------------------------------------------
status_start = "# ============================================================\n# SOURCE STATUS\n# ============================================================\n"
status_end = "# ============================================================\n# PRESET\n# ============================================================\n"
if "Data Status · details" in app and status_start in app and status_end in app:
    i = app.index(status_start)
    j = app.index(status_end, i)
    replacement = (
        status_start
        + "\n# Source validation remains active behind the scenes.\n"
        + "if with_projection == 0:\n"
        + "    st.error(\"No players have resolved projections. Check the slate data files before generating.\")\n"
        + "    st.stop()\n\n\n"
    )
    app = app[:i] + replacement + app[j:]

# ---------------------------------------------------------------------------
# 2) Hide Show Research + DVP helper text robustly.
# ---------------------------------------------------------------------------
if "Show research columns" in app:
    lines = app.splitlines(keepends=True)
    start, end = find_call_span(lines, "Show research columns", "st.checkbox(")

    # Preserve the assignment target regardless of whether call is one or many lines.
    assignment_line = lines[start]
    indent = assignment_line[: len(assignment_line) - len(assignment_line.lstrip())]
    if "show_research" not in "".join(lines[start:end]):
        fail("Located research checkbox but could not confirm show_research assignment")
    lines[start:end] = [f"{indent}show_research = False\n"]
    app = "".join(lines)

# Remove DVP helper captions; backing data/column stays intact.
app = re.sub(
    r'(?m)^\s*st\.caption\(\s*"DVP · green[^\n]*\n',
    '',
    app,
    count=1,
)
app = re.sub(
    r'(?ms)^\s*if not dvp_values:\s*\n\s*st\.caption\(dvp_status\)\s*\n',
    '\n',
    app,
    count=1,
)

# ---------------------------------------------------------------------------
# 3) Move Position widget only; leave existing sort controls untouched.
# ---------------------------------------------------------------------------
lines = app.splitlines(keepends=True)
start, end = find_call_span(lines, 'key="active_position"', 'active_position = st.radio(')

# If radio is nested inside a one-purpose `with ...:` column, remove that wrapper too.
call_indent = len(lines[start]) - len(lines[start].lstrip())
wrapper_start = start
prev = start - 1
while prev >= 0 and not lines[prev].strip():
    prev -= 1
if prev >= 0:
    prev_indent = len(lines[prev]) - len(lines[prev].lstrip())
    if lines[prev].lstrip().startswith("with ") and lines[prev].rstrip().endswith(":") and prev_indent < call_indent:
        wrapper_start = prev
lines[wrapper_start:end] = []
app = "".join(lines)

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
    fail("Could not locate Player Pool table-control anchor")

position_block = '''    # Position filter sits immediately above the Player Pool table.\n    position_controls = st.columns([6.7, 3.3])\n    with position_controls[0]:\n        active_position = st.radio(\n            "Position",\n            options=["ALL", "QB", "RB", "WR", "TE", "DST"],\n            horizontal=True,\n            key="active_position",\n            label_visibility="collapsed",\n        )\n\n'''
app = app.replace(anchor, position_block + anchor, 1)

# ---------------------------------------------------------------------------
# 4) Nudge bulk Min/Max down slightly.
# ---------------------------------------------------------------------------
for idx, label in ((2, "Min %"), (3, "Max %")):
    marker = f'''        with header_controls[{idx}]:\n            st.number_input(\n                "{label}",\n'''
    replacement = f'''        with header_controls[{idx}]:\n            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)\n            st.number_input(\n                "{label}",\n'''
    if marker in app and "height:8px" not in app:
        app = app.replace(marker, replacement, 1)

# ---------------------------------------------------------------------------
# 5) Clean compact lineup header without markdown-dollar ambiguity.
# ---------------------------------------------------------------------------
# Replace the whole compact lineup summary st.markdown call by locating L{original_number}.
if "L{original_number}" in app:
    lines = app.splitlines(keepends=True)
    start, end = find_call_span(lines, "L{original_number}", "st.markdown(")
    indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    clean = (
        f'{indent}st.markdown(\n'
        f'{indent}    f"<strong>L{{original_number}}</strong> &nbsp;·&nbsp; "\n'
        f'{indent}    f"Proj <strong>{{lineup.projection:.1f}}</strong> &nbsp;·&nbsp; "\n'
        f'{indent}    f"Ceil <strong>{{ceiling_text}}</strong> &nbsp;·&nbsp; "\n'
        f'{indent}    f"Own <strong>{{own_text}}</strong> &nbsp;·&nbsp; "\n'
        f'{indent}    f"Salary <strong>&#36;{{lineup.salary:,}}</strong> &nbsp;·&nbsp; "\n'
        f'{indent}    f"Left <strong>&#36;{{50_000 - lineup.salary:,}}</strong>",\n'
        f'{indent}    unsafe_allow_html=True,\n'
        f'{indent})\n'
    )
    lines[start:end] = [clean]
    app = "".join(lines)

# ---------------------------------------------------------------------------
# 6) Add generated ownership diagnostic + partial-generation warning.
# ---------------------------------------------------------------------------
if 'Ownership constraint:' not in app:
    summary_anchor = '''    reservoir_metrics[4].metric(\n        "Mean Overlap",\n        f"{summary['mean_overlap']:.2f}",\n    )\n\n'''
    if summary_anchor not in app:
        fail("Could not locate generated summary anchor")

    diagnostic = '''    reservoir_metrics[4].metric(\n        "Mean Overlap",\n        f"{summary['mean_overlap']:.2f}",\n    )\n\n    generated_ownerships = [\n        float(lineup.ownership)\n        for lineup in lineups\n        if lineup.ownership is not None\n    ]\n    if generated_settings is not None:\n        own_min_setting = generated_settings.ownership_min\n        own_max_setting = generated_settings.ownership_max\n        if own_min_setting is None and own_max_setting is None:\n            ownership_constraint_label = "OFF"\n        elif own_min_setting is not None and own_max_setting is None:\n            ownership_constraint_label = f"MIN {own_min_setting:.0f}%"\n        elif own_min_setting is None and own_max_setting is not None:\n            ownership_constraint_label = f"MAX {own_max_setting:.0f}%"\n        else:\n            ownership_constraint_label = f"{own_min_setting:.0f}%–{own_max_setting:.0f}%"\n    else:\n        ownership_constraint_label = "Unknown"\n\n    if generated_ownerships:\n        ownership_series = pd.Series(generated_ownerships)\n        st.caption(\n            f"Ownership constraint: {ownership_constraint_label} · "\n            f"Generated min/median/max: {ownership_series.min():.1f}% / "\n            f"{ownership_series.median():.1f}% / {ownership_series.max():.1f}%"\n        )\n    else:\n        st.caption(f"Ownership constraint: {ownership_constraint_label} · Generated ownership unavailable")\n\n    if generated_settings is not None and len(lineups) < int(generated_settings.num_lineups):\n        st.warning(\n            f"Generated {len(lineups)} / {int(generated_settings.num_lineups)} — "\n            "remaining lineups were infeasible under the current constraints."\n        )\n\n'''
    app = app.replace(summary_anchor, diagnostic, 1)

# ---------------------------------------------------------------------------
# Validate BEFORE writing.
# ---------------------------------------------------------------------------
compile(app, str(APP), "exec")

checks = {
    "position_filter_moved": app.count('key="active_position"') == 1 and 'position_controls = st.columns' in app,
    "research_helper_hidden": 'show_research = False' in app and 'Show research columns' not in app,
    "dvp_helper_hidden": 'DVP · green' not in app and 'DVP unavailable:' not in app,
    "html_leak_removed": '\\$' not in app and 'Salary <strong>&#36;' in app,
    "ownership_diagnostic_added": 'Ownership constraint:' in app,
    "source_details_hidden": 'Data Status · details' not in app,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    fail("Verification failed before write: " + ", ".join(failed))

backup_dir = ROOT / "repair_backup_20261029"
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "app_before_ui_cleanup_v8d.py"
if not backup.exists():
    backup.write_text(original, encoding="utf-8")

APP.write_text(app, encoding="utf-8")

print("Applied UI cleanup V8d")
for name, ok in checks.items():
    print(f"VERIFY {name}: {ok}")
print("Optimizer math unchanged")
