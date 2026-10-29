from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
THEME = ROOT / "ui_theme.py"


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    i = text.find(start)
    if i < 0:
        raise RuntimeError(f"Start marker not found: {start!r}")
    j = text.find(end, i)
    if j < 0:
        raise RuntimeError(f"End marker not found: {end!r}")
    return text[:i] + replacement + text[j:]


app = APP.read_text(encoding="utf-8")
theme = THEME.read_text(encoding="utf-8")

# 1) Add compact bulk-exposure + sentiment mapping helpers.
needle = '''def _save_pool_edits(editor_key, player_ids):\n'''
helpers = '''def _apply_position_exposure(position, player_ids, changed_field):\n    min_key = f"group_exposure_min_{position}"\n    max_key = f"group_exposure_max_{position}"\n    min_value = int(st.session_state.get(min_key, 0))\n    max_value = int(st.session_state.get(max_key, 100))\n\n    # Keep the pair legal while preserving the field the user just changed.\n    if min_value > max_value:\n        if changed_field == "Min %":\n            max_value = min_value\n            st.session_state[max_key] = max_value\n        else:\n            min_value = max_value\n            st.session_state[min_key] = min_value\n\n    for pid in player_ids:\n        controls = st.session_state.player_controls[pid]\n        controls["Min %"] = min_value\n        controls["Max %"] = max_value\n\n    st.session_state.pool_editor_revision = st.session_state.get("pool_editor_revision", 0) + 1\n\n\nSENTIMENT_DISPLAY_TO_STATE = {\n    sentiment_display(state): state\n    for state in PLAYER_SENTIMENT_OPTIONS\n}\n\n\ndef _sentiment_state(value):\n    raw = str(value)\n    return SENTIMENT_DISPLAY_TO_STATE.get(raw, raw.upper())\n\n\n'''
if helpers not in app:
    if needle not in app:
        raise RuntimeError("Could not find _save_pool_edits insertion point")
    app = app.replace(needle, helpers + needle, 1)

# Make row sentiment edits use the display-label mapping.
app = app.replace(
    'elif column == "Sentiment":\n                controls[column] = str(value).upper()',
    'elif column == "Sentiment":\n                controls[column] = _sentiment_state(value)',
)

# 2) Remove the old standalone position-wide exposure panel.
start = '''    # --------------------------------------------------------\n    # POSITION-WIDE EXPOSURE CONTROLS\n'''
end = '''    # --------------------------------------------------------\n    # QUICK FILTERS\n'''
app = replace_between(app, start, end, end)

# 3) Replace Locked Players + old standalone In Pool control with compact header controls.
start = '''    # Preserve Lock capability without a second checkbox column.\n'''
end = '''    # --------------------------------------------------------\n    # PLAYER TABLE\n'''
replacement = '''    # Lock capability remains available in the optimizer engine, but the UI\n    # intentionally exposes no hidden/secondary lock control. Clear any stale\n    # session locks so what the user sees is what generation uses.\n    for controls in st.session_state.player_controls.values():\n        controls["Lock"] = False\n\n    visible_ids = [int(player.dk_id) for player in filtered_players]\n    all_visible_in_pool = bool(visible_ids) and all(\n        not st.session_state.player_controls[dk_id].get("Exclude", False)\n        for dk_id in visible_ids\n    )\n\n    # DS-style compact table controls. The master pool checkbox acts on the\n    # currently shown rows. Min/Max act on the active position only, matching\n    # the established QB/RB/WR/TE/DST bulk-edit contract.\n    header_controls = st.columns([0.85, 7.15, 1.0, 1.0])\n\n    select_all_key = f"in_pool_all_{active_position}"\n    st.session_state[select_all_key] = all_visible_in_pool\n    with header_controls[0]:\n        st.checkbox(\n            "In Pool",\n            key=select_all_key,\n            help="Check or uncheck every player currently shown below. Unchecked players stay visible.",\n            on_change=_set_visible_pool,\n            args=(select_all_key, visible_ids),\n        )\n\n    bulk_positions = {"QB", "RB", "WR", "TE", "DST"}\n    if active_position in bulk_positions:\n        position_ids = [\n            int(player.dk_id)\n            for player in available\n            if player.position == active_position\n        ]\n        current_mins = {\n            int(st.session_state.player_controls[pid]["Min %"])\n            for pid in position_ids\n        }\n        current_maxes = {\n            int(st.session_state.player_controls[pid]["Max %"])\n            for pid in position_ids\n        }\n        min_key = f"group_exposure_min_{active_position}"\n        max_key = f"group_exposure_max_{active_position}"\n        if min_key not in st.session_state:\n            st.session_state[min_key] = next(iter(current_mins)) if len(current_mins) == 1 else 0\n        if max_key not in st.session_state:\n            st.session_state[max_key] = next(iter(current_maxes)) if len(current_maxes) == 1 else 100\n\n        with header_controls[2]:\n            st.number_input(\n                "Min %",\n                min_value=0,\n                max_value=100,\n                step=5,\n                key=min_key,\n                on_change=_apply_position_exposure,\n                args=(active_position, position_ids, "Min %"),\n            )\n        with header_controls[3]:\n            st.number_input(\n                "Max %",\n                min_value=0,\n                max_value=100,\n                step=5,\n                key=max_key,\n                on_change=_apply_position_exposure,\n                args=(active_position, position_ids, "Max %"),\n            )\n    else:\n        with header_controls[2]:\n            st.number_input("Min %", 0, 100, 0, 5, disabled=True, key="all_bulk_min_disabled")\n        with header_controls[3]:\n            st.number_input("Max %", 0, 100, 100, 5, disabled=True, key="all_bulk_max_disabled")\n\n\n'''
app = replace_between(app, start, end, replacement + end)

# 4) Remove the giant standalone sentiment picker/button strip.
start = '''    if filtered_players:\n        sentiment_players = {int(p.dk_id): p for p in filtered_players}\n'''
end = '''    show_research = st.checkbox("Show research columns", value=False)\n'''
app = replace_between(app, start, end, end)

# 5) Convert the table to direct row-level Sentiment and add a DVP placeholder column.
app = app.replace(
    '''                "Sentiment": controls.get(\n                    "Sentiment",\n                    "NEUTRAL",\n                ),''',
    '''                "Sentiment": sentiment_display(controls.get(\n                    "Sentiment",\n                    "NEUTRAL",\n                )),''',
    1,
)
app = app.replace(
    '''                "Visual": player_visual_uri(p, BASE_DIR / "assets"),\n                "Conviction": sentiment_display(controls.get("Sentiment", "NEUTRAL")),\n                "Team": p.team,\n                "Opp": p.opponent,''',
    '''                "Visual": player_visual_uri(p, BASE_DIR / "assets"),\n                "Team": p.team,\n                "Opp": p.opponent,\n                # Real DVP is not present in the current verified slate evidence.\n                # Keep the UI slot explicit rather than relabeling Matchup_Score.\n                "DVP": "—",''',
    1,
)
app = app.replace(
    '''        "In Pool", "Visual", "Player", "Team", "Opp", "Pos", "Salary", "Proj",\n        "Own %", "Ceiling", "Value", "Conviction", "Min %", "Max %", "ID",\n        "Sentiment", "Role", "Form", "Matchup", "Env", "Edge", "Injury", "Status",''',
    '''        "In Pool", "Visual", "Player", "Team", "Opp", "DVP", "Pos", "Salary", "Proj",\n        "Own %", "Ceiling", "Value", "Sentiment", "Min %", "Max %", "ID",\n        "Role", "Form", "Matchup", "Env", "Edge", "Injury", "Status",''',
    1,
)
app = app.replace(
    '''    display_columns = ["In Pool", "Visual", "Player", "Team", "Opp", "Pos", "Salary",\n                       "Proj", "Own %", "Ceiling", "Value", "Conviction", "Min %", "Max %"]''',
    '''    display_columns = ["In Pool", "Visual", "Player", "Pos", "Team", "Opp", "DVP", "Salary",\n                       "Proj", "Own %", "Ceiling", "Value", "Sentiment", "Min %", "Max %"]''',
    1,
)
app = app.replace(
    '''            "Visual", "Conviction", "Sentiment",\n            "ID",''',
    '''            "Visual", "DVP",\n            "ID",''',
    1,
)
app = app.replace(
    '''            "Sentiment": None,\n            "Visual": st.column_config.ImageColumn("", width=35),\n            "Player": st.column_config.TextColumn("Player", width="medium"),\n            "Conviction": st.column_config.TextColumn("Sentiment", width="small"),''',
    '''            "Visual": st.column_config.ImageColumn("", width=35),\n            "Player": st.column_config.TextColumn("Player", width="medium"),\n            "DVP": st.column_config.TextColumn(\n                "DVP",\n                width="small",\n                help="Defense-vs-position rank. Current verified slate source does not provide DVP, so missing values remain —.",\n            ),\n            "Sentiment": st.column_config.SelectboxColumn(\n                "Sentiment",\n                options=[sentiment_display(state) for state in PLAYER_SENTIMENT_OPTIONS],\n                required=True,\n                width="small",\n                help="Objective-only sentiment adjustment; displayed projection remains unchanged.",\n            ),''',
    1,
)

# Map editable display labels back to optimizer states after the editor.
app = app.replace(
    '''    sentiment = str(row["Sentiment"]).upper()''',
    '''    sentiment = _sentiment_state(row["Sentiment"])''',
    1,
)

# 6) Remove the visible Locked summary metric; preserve engine support as an empty set.
old_summary = '''control_cols = st.columns(4)\n\ncontrol_cols[0].metric(\n    "Locked",\n    len(\n        settings.lock_players\n    ),\n)\n\ncontrol_cols[1].metric(\n    "Excluded",\n    len(\n        settings.exclude_players\n    ),\n)\n\ncontrol_cols[2].metric(\n    "Exposure Overrides",\n    len(\n        set(\n            settings.player_min_exposure\n        )\n        | set(\n            settings.player_max_exposure\n        )\n    ),\n)\n\ncontrol_cols[3].metric(\n    "Projection Coverage",\n    f"{with_projection}/{len(players)}",\n)\n'''
new_summary = '''control_cols = st.columns(3)\n\ncontrol_cols[0].metric(\n    "Excluded",\n    len(settings.exclude_players),\n)\n\ncontrol_cols[1].metric(\n    "Exposure Overrides",\n    len(set(settings.player_min_exposure) | set(settings.player_max_exposure)),\n)\n\ncontrol_cols[2].metric(\n    "Projection Coverage",\n    f"{with_projection}/{len(players)}",\n)\n'''
if old_summary not in app:
    raise RuntimeError("Could not find Player Control Summary block")
app = app.replace(old_summary, new_summary, 1)

# 7) Suppress Streamlit stale-element dimming during quick number-input reruns.
css_needle = '''    [data-testid="stDataFrame"] {{\n        border: 1px solid var(--dc-border);\n        border-radius: 9px;\n        overflow: hidden;\n    }}\n'''
css_add = css_needle + '''\n    /* Keep rapid exposure clicks from visually stacking Streamlit's stale-state dimming. */\n    .stale-element, [data-stale="true"] {{\n        opacity: 1 !important;\n        filter: none !important;\n    }}\n'''
if css_needle not in theme:
    raise RuntimeError("Could not find dataframe CSS insertion point")
theme = theme.replace(css_needle, css_add, 1)

APP.write_text(app, encoding="utf-8")
THEME.write_text(theme, encoding="utf-8")
print("Applied compact Player Pool target UI to app.py and ui_theme.py")
