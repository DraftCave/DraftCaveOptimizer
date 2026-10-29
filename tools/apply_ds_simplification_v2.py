from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Could not find {label}; local app.py may differ from the expected UI checkpoint.")
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8")

# Require the first compact Player Pool patch before applying this follow-up.
for marker in (
    '"DVP": "—"',
    'group_exposure_min_',
    'show_research_columns_v5',
):
    if marker not in app:
        raise RuntimeError(
            "This patch expects the compact Player Pool checkpoint. "
            f"Missing marker: {marker}"
        )

# ---------------------------------------------------------------------------
# 1) Sentiment: remove the data-editor dropdown. Keep the compact current state
#    in the row and add a DS-like horizontal one-click pill strip above the pool.
# ---------------------------------------------------------------------------

old_disabled = '''        disabled=[
            "Visual", "DVP",
            "ID",
'''
new_disabled = '''        disabled=[
            "Visual", "DVP", "Sentiment",
            "ID",
'''
app = replace_once(app, old_disabled, new_disabled, "Player Pool disabled-column list")

old_sentiment_config = '''            "Sentiment": st.column_config.SelectboxColumn(
                "Sentiment",
                options=[sentiment_display(state) for state in PLAYER_SENTIMENT_OPTIONS],
                required=True,
                width="small",
                help="Objective-only sentiment adjustment; displayed projection remains unchanged.",
            ),'''
new_sentiment_config = '''            "Sentiment": st.column_config.TextColumn(
                "Sentiment",
                width="small",
                help="Current objective-only sentiment. Use Quick Sentiment above for one-click changes.",
            ),'''
app = replace_once(app, old_sentiment_config, new_sentiment_config, "Sentiment column config")

quick_sentiment_anchor = '''    show_research = st.checkbox("Show research columns", value=False, key="show_research_columns_v5")
'''
quick_sentiment_block = '''    # DS-style Quick Sentiment: choose a player once, then use one-click horizontal pills.
    # Stock Streamlit data_editor cannot open a true inline cell popover, so this keeps
    # the interaction compact without a double-click vertical dropdown.
    if filtered_players:
        quick_sentiment_players = {int(player.dk_id): player for player in filtered_players}
        quick_cols = st.columns([2.4, 5.6])
        with quick_cols[0]:
            quick_sentiment_id = st.selectbox(
                "Quick Sentiment Player",
                options=list(quick_sentiment_players),
                format_func=lambda pid: (
                    f"{quick_sentiment_players[pid].name} · "
                    f"{quick_sentiment_players[pid].team} {quick_sentiment_players[pid].position}"
                ),
                key=f"quick_sentiment_player_{active_position}",
                label_visibility="collapsed",
            )
        current_quick_sentiment = str(
            st.session_state.player_controls[quick_sentiment_id].get("Sentiment", "NEUTRAL")
        ).upper()
        with quick_cols[1]:
            quick_sentiment = st.pills(
                "Sentiment",
                options=PLAYER_SENTIMENT_OPTIONS,
                default=current_quick_sentiment,
                required=True,
                format_func=lambda state: SENTIMENT_UI[state]["icon"],
                key=f"quick_sentiment_pills_{quick_sentiment_id}",
                help=(
                    "😍 Adore · ❤️ Love · 🙂 Like · 😐 Neutral · "
                    "🙁 Dislike · 😡 Hate · ⛔ Ban"
                ),
                label_visibility="collapsed",
                width="content",
                wrap=False,
            )
        if quick_sentiment and quick_sentiment != current_quick_sentiment:
            _set_sentiment(quick_sentiment_id, quick_sentiment)
            st.rerun()

    show_research = st.checkbox("Show research columns", value=False, key="show_research_columns_v5")
'''
app = replace_once(app, quick_sentiment_anchor, quick_sentiment_block, "Quick Sentiment insertion point")

# The row now stores a display label, but the post-editor save path already maps
# display labels through _sentiment_state. No optimizer semantics change.

# ---------------------------------------------------------------------------
# 2) Generated portfolio: make the first/default tab the DS-style working view.
#    Exposure and lineup usage are visible together and controlled by one
#    ALL/QB/RB/WR/TE/DST position bar.
# ---------------------------------------------------------------------------

app = replace_once(
    app,
    '''            "Lineups",
            "Exposure",
            "Stacks & Games",
            "Portfolio Risk",
            "Repetition",
            "Export",
''',
    '''            "Portfolio Review",
            "Stacks & Games",
            "Portfolio Risk",
            "Repetition",
            "Export",
''',
    "generated tab labels",
)

old_lineup_tab = '''    with tabs[0]:

        lineup_view_position = st.radio(
            "Lineup position view",
            options=["ALL", "QB", "RB", "WR", "TE", "DST"],
            horizontal=True,
            key="generated_lineup_position_view",
            label_visibility="collapsed",
        )

        if lineup_view_position == "ALL":
            st.caption(
                "Full roster view. Select a position to scan that position across every generated lineup."
            )
        else:
            st.caption(
                f"{lineup_view_position} view across all {len(lineups)} generated lineups."
            )

        show_table(
            position_lineup_table(
                lineups,
                lineup_view_position,
            ),
            width="stretch",
            height=600,
        )


    # --------------------------------------------------------
    # PLAYER EXPOSURES
    # --------------------------------------------------------

    with tabs[1]:

        exp_left, exp_mid, exp_right = (
            st.columns(3)
        )

        with exp_left:

            st.markdown(
                "### Player Exposure"
            )

            show_table(
                player_exposure(
                    lineups
                ),
                width="stretch",
            )

        with exp_mid:

            st.markdown(
                "### QB Exposure"
            )

            show_table(
                qb_exposure(
                    lineups
                ),
                width="stretch",
            )

        with exp_right:

            st.markdown(
                "### FLEX Distribution"
            )

            show_table(
                flex_distribution(
                    lineups
                ),
                width="stretch",
            )


'''
new_lineup_tab = '''    with tabs[0]:

        review_position = st.radio(
            "Portfolio review position",
            options=["ALL", "QB", "RB", "WR", "TE", "DST"],
            horizontal=True,
            key="generated_portfolio_review_position",
            label_visibility="collapsed",
        )

        st.caption(
            "Review exposure and how the generated lineups use that position in one place. "
            "Click any table header to sort."
        )

        review_exposure = player_exposure(lineups).copy()
        if review_position != "ALL":
            review_exposure = review_exposure.loc[
                review_exposure["Position"] == review_position
            ].copy()

        control_lookup = {
            (player.name, player.position, player.team): st.session_state.player_controls.get(int(player.dk_id), {})
            for player in available
        }
        review_exposure["Min %"] = [
            int(control_lookup.get((row.Name, row.Position, row.Team), {}).get("Min %", 0))
            for row in review_exposure.itertuples(index=False)
        ]
        review_exposure["Max %"] = [
            int(control_lookup.get((row.Name, row.Position, row.Team), {}).get("Max %", 100))
            for row in review_exposure.itertuples(index=False)
        ]

        review_left, review_right = st.columns([1.0, 2.25])

        with review_left:
            st.markdown(
                f"### {'All Player' if review_position == 'ALL' else review_position} Exposure"
            )
            exposure_columns = [
                "Name", "Team", "Position", "Count", "Exposure", "Min %", "Max %"
            ]
            show_table(
                review_exposure[exposure_columns],
                width="stretch",
                height=560,
            )

            if review_position == "ALL":
                st.markdown("#### FLEX Mix")
                show_table(
                    flex_distribution(lineups),
                    width="stretch",
                )

        with review_right:
            st.markdown(
                f"### {'Full Lineups' if review_position == 'ALL' else review_position + ' Usage'} · {len(lineups)} generated"
            )
            show_table(
                position_lineup_table(lineups, review_position),
                width="stretch",
                height=620,
            )


'''
app = replace_once(app, old_lineup_tab, new_lineup_tab, "generated Portfolio Review block")

# Shift the remaining tab indexes left because the standalone Exposure tab is gone.
# Use exact block-open replacements so nested references are not touched accidentally.
app = app.replace('    with tabs[4]:\n\n        stack_left, stack_right', '    with tabs[3]:\n\n        stack_left, stack_right', 1)
app = app.replace('    with tabs[3]:\n\n        st.markdown(\n            "### Portfolio Summary"', '    with tabs[2]:\n\n        st.markdown(\n            "### Portfolio Summary"', 1)
app = app.replace('    with tabs[2]:\n\n        st.markdown(\n            "### QB / Game / Stack Story Families"', '    with tabs[1]:\n\n        st.markdown(\n            "### QB / Game / Stack Story Families"', 1)
app = app.replace('    with tabs[3]:\n\n        st.markdown(\n            "### Outcome-Blind Final Selection"', '    with tabs[2]:\n\n        st.markdown(\n            "### Outcome-Blind Final Selection"', 1)
app = app.replace('    with tabs[5]:\n\n        st.markdown(\n            "### DraftKings Export"', '    with tabs[4]:\n\n        st.markdown(\n            "### DraftKings Export"', 1)

# ---------------------------------------------------------------------------
# 3) Compile before writing so a failed transform cannot leave a syntax-broken app.
# ---------------------------------------------------------------------------

compile(app, str(APP), "exec")

backup = ROOT / "repair_backup_20261029" / "app_before_ds_simplification_v2.py"
backup.parent.mkdir(parents=True, exist_ok=True)
if not backup.exists():
    backup.write_text(APP.read_text(encoding="utf-8"), encoding="utf-8")

APP.write_text(app, encoding="utf-8")
print("Applied DS-style simplification V2 to app.py")
print("- Quick Sentiment uses horizontal one-click pills")
print("- Portfolio Review shows position exposure beside generated lineup usage")
print("- Standalone Exposure tab removed; deeper analysis remains available")
