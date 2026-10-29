from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def fail(message: str) -> None:
    raise RuntimeError(message)


original = APP.read_text(encoding="utf-8")
app = original

# Exact local-state anchors captured by tools/inspect_local_ui_context.py.
position_block = '''    position_row = st.columns([5.0, 5.0])
    with position_row[0]:
        active_position = st.radio(
            "Position",
            options=["ALL", "QB", "RB", "WR", "TE", "DST"],
            horizontal=True,
            key="active_position",
            label_visibility="collapsed",
        )

'''
header_anchor = '''    # DS-style compact table controls. The master pool checkbox acts on the
    # currently shown rows. Min/Max act on the active position only, matching
    # the established QB/RB/WR/TE/DST bulk-edit contract.
    header_controls = st.columns([0.85, 7.0, 1.075, 1.075])
'''
research_block = '''    show_research = st.checkbox("Show research columns", value=False, key="show_research_columns_v5")

    st.caption("DVP · green 1–8 · yellow 9–16 · orange 17–24 · red 25–32 · 1 = easiest. Visual only. Missing = —.")
    if not dvp_values:
        st.caption(dvp_status)

'''

for label, needle in (
    ("position block", position_block),
    ("header anchor", header_anchor),
    ("research/DVP block", research_block),
):
    if needle not in app:
        fail(f"Could not find exact local {label}; run the inspector again before patching.")

# 1) Move Position to directly above the table controls.
app = app.replace(position_block, "", 1)
app = app.replace(header_anchor, position_block + header_anchor, 1)

# 2) Hide the research toggle and DVP explanatory clutter, preserving backing data.
app = app.replace(research_block, "    show_research = False\n\n", 1)

# 3) Nudge Min/Max controls down slightly in BOTH active-position and ALL-disabled branches.
for idx in (2, 3):
    marker = f"        with header_controls[{idx}]:\n"
    spacer = marker + "            st.markdown(\"<div style='height:8px'></div>\", unsafe_allow_html=True)\n"
    # There are two branches for each control. Add the spacer to each occurrence that
    # does not already have one immediately after the with-block.
    start = 0
    while True:
        i = app.find(marker, start)
        if i == -1:
            break
        after = i + len(marker)
        if not app.startswith("            st.markdown(\"<div style='height:8px'></div>\", unsafe_allow_html=True)\n", after):
            app = app[:after] + "            st.markdown(\"<div style='height:8px'></div>\", unsafe_allow_html=True)\n" + app[after:]
            start = after + 90
        else:
            start = after

# 4) Fix the Python warning while keeping a literal dollar sign in Streamlit markdown.
# Source must contain two backslashes so the runtime string contains `\$` for markdown.
app = app.replace(
    'f"Salary **\\${lineup.salary:,}**  ·  "',
    'f"Salary **\\\\${lineup.salary:,}**  ·  "',
)
app = app.replace(
    'f"Left **\\${50_000 - lineup.salary:,}**"',
    'f"Left **\\\\${50_000 - lineup.salary:,}**"',
)

# Compile before writing.
compile(app, str(APP), "exec")

checks = {
    "position_now_above_header_controls": app.index('key="active_position"') < app.index('header_controls = st.columns'),
    "research_checkbox_hidden": 'st.checkbox("Show research columns"' not in app and 'show_research = False' in app,
    "dvp_helper_hidden": 'DVP · green' not in app and 'st.caption(dvp_status)' not in app,
    "minmax_spacers_added": app.count("<div style='height:8px'></div>") >= 2,
    "salary_escape_warning_fixed": 'Salary **\\${lineup.salary' not in app and 'Salary **\\\\${lineup.salary' in app,
    "ownership_diagnostic_preserved": 'Ownership constraint:' in app,
    "data_status_details_remain_hidden": 'Data Status · details' not in app,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    fail("Verification failed before write: " + ", ".join(failed))

backup_dir = ROOT / "repair_backup_20261029"
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "app_before_ui_cleanup_v8e.py"
if not backup.exists():
    backup.write_text(original, encoding="utf-8")

APP.write_text(app, encoding="utf-8")

print("Applied UI cleanup V8e")
for name, ok in checks.items():
    print(f"VERIFY {name}: {ok}")
print("Optimizer math unchanged")
