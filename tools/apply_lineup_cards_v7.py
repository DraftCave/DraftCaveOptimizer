from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Could not find {label}; local app.py may differ from the V6 checkpoint.")
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8")

# Require V6 checkpoint markers.
for marker in (
    'key="pool_sort_direction_v6"',
    'key="generated_lineup_sort_v6"',
    'Each lineup is shown as a vertical card.',
):
    if marker not in app:
        raise RuntimeError(f"Expected V6 marker missing: {marker}")

# ---------------------------------------------------------------------------
# 1) Make persistent sorting fast and obvious.
#    Streamlit's native table-header sort is browser-side only and cannot be
#    recovered after an editor rerun, so this is the canonical live-build sort.
# ---------------------------------------------------------------------------
old_pool_nav = '''    # Keep the two controls used most often during live builds attached to the table.\n    pool_nav = st.columns([5.6, 2.2, 2.2])\n    with pool_nav[0]:\n        active_position = st.radio(\n            "Position",\n            options=["ALL", "QB", "RB", "WR", "TE", "DST"],\n            horizontal=True,\n            key="active_position",\n            label_visibility="collapsed",\n        )\n    with pool_nav[1]:\n        pool_sort = st.selectbox(\n            "Persistent Sort",\n            ["Salary", "Own %", "Proj", "Base Proj", "Ceiling", "Value", "Player", "DVP", "Min %", "Max %"],\n            key="pool_sort",\n        )\n    with pool_nav[2]:\n        pool_sort_direction = st.selectbox(\n            "Order",\n            ["↓ High to low", "↑ Low to high"],\n            key="pool_sort_direction_v6",\n        )\n'''
new_pool_nav = '''    # Canonical persistent sort. Clicking a Streamlit table header is temporary;\n    # these controls survive checkbox/sentiment/exposure edits and reruns.\n    pool_nav = st.columns([4.9, 3.8, 1.3])\n    with pool_nav[0]:\n        active_position = st.radio(\n            "Position",\n            options=["ALL", "QB", "RB", "WR", "TE", "DST"],\n            horizontal=True,\n            key="active_position",\n            label_visibility="collapsed",\n        )\n    with pool_nav[1]:\n        pool_sort = st.radio(\n            "Sort by",\n            ["Salary", "Own %", "Proj", "Ceiling", "Value", "Player", "DVP"],\n            horizontal=True,\n            key="pool_sort",\n            label_visibility="collapsed",\n        )\n    with pool_nav[2]:\n        pool_sort_direction = st.selectbox(\n            "Order",\n            ["↓", "↑"],\n            key="pool_sort_direction_v7",\n            label_visibility="collapsed",\n        )\n    st.caption("Persistent sort stays active after player-pool edits. Use this row instead of clicking a table header when you want the order preserved.")\n'''
app = replace_once(app, old_pool_nav, new_pool_nav, "Player Pool navigation/sort controls")
app = replace_once(
    app,
    'pool_df = sort_pool(pool_df, pool_sort, pool_sort_direction.startswith("↓"))',
    'pool_df = sort_pool(pool_df, pool_sort, pool_sort_direction == "↓")',
    "Player Pool persistent sort application",
)

# ---------------------------------------------------------------------------
# 2) Replace full-width lineup report cards with two compact DS-style cards per
#    row. Players remain vertically stacked; Team/Opp use the same logo+abbr
#    visual cells already used by the Player Pool.
# ---------------------------------------------------------------------------
start = '''            st.caption(\n                "Each lineup is shown as a vertical card. Projection, ceiling, ownership, salary and salary left are visible before the roster."\n            )\n\n            slot_order = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "DST"]\n            for original_number, lineup in indexed_lineups:\n'''
end = '''\n        else:\n            review_exposure = player_exposure(lineups).copy()\n'''
if start not in app or end not in app:
    raise RuntimeError("Could not find V6 lineup-card block")
i = app.index(start)
j = app.index(end, i)
new_cards = '''            st.caption(\n                "Compact vertical lineup cards · two per row · Team/Opp logos included."\n            )\n\n            slot_order = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "DST"]\n            for pair_start in range(0, len(indexed_lineups), 2):\n                card_cols = st.columns(2)\n                pair = indexed_lineups[pair_start:pair_start + 2]\n                for card_col, (original_number, lineup) in zip(card_cols, pair):\n                    with card_col:\n                        with st.container(border=True):\n                            ceiling_text = "—" if lineup.ceiling is None else f"{lineup.ceiling:.1f}"\n                            own_text = "—" if lineup.ownership is None else f"{lineup.ownership:.1f}%"\n                            st.markdown(\n                                f"**L{original_number}** &nbsp; · &nbsp; "\n                                f"Proj **{lineup.projection:.1f}** &nbsp; · &nbsp; "\n                                f"Ceil **{ceiling_text}** &nbsp; · &nbsp; "\n                                f"Own **{own_text}** &nbsp; · &nbsp; "\n                                f"${lineup.salary:,} &nbsp; · &nbsp; Left **${50_000 - lineup.salary:,}**"\n                            )\n\n                            roster_rows = []\n                            for slot in slot_order:\n                                player = lineup.slots.get(slot)\n                                if player is None:\n                                    continue\n                                roster_rows.append(\n                                    {\n                                        "Pos": slot,\n                                        "Player": player.name,\n                                        "Team": team_cell_uri(player.team, str(BASE_DIR / "assets")),\n                                        "Opp": team_cell_uri(player.opponent, str(BASE_DIR / "assets")),\n                                        "Sal": player.salary,\n                                        "Proj": player.projection,\n                                        "Own": player.ownership,\n                                    }\n                                )\n\n                            roster_df = pd.DataFrame(roster_rows)\n                            st.dataframe(\n                                roster_df,\n                                width="stretch",\n                                height=332,\n                                row_height=30,\n                                hide_index=True,\n                                column_config={\n                                    "Pos": st.column_config.TextColumn("Pos", width="small"),\n                                    "Player": st.column_config.TextColumn("Player", width="medium"),\n                                    "Team": st.column_config.ImageColumn("Team", width=64),\n                                    "Opp": st.column_config.ImageColumn("Opp", width=64),\n                                    "Sal": st.column_config.NumberColumn("Sal", format="$%d", width="small"),\n                                    "Proj": st.column_config.NumberColumn("Proj", format="%.1f", width="small"),\n                                    "Own": st.column_config.NumberColumn("Own", format="%.1f", width="small"),\n                                },\n                            )\n'''
app = app[:i] + new_cards + app[j:]

compile(app, str(APP), "exec")

backup_dir = ROOT / "repair_backup_20261029"
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "app_before_lineup_cards_v7.py"
if not backup.exists():
    backup.write_text(APP.read_text(encoding="utf-8"), encoding="utf-8")

APP.write_text(app, encoding="utf-8")
print("Applied lineup review V7")
print("- persistent Player Pool sort is now a one-click control row")
print("- generated lineup cards are compact and two-per-row")
print("- players are vertically stacked QB through DST")
print("- Team/Opp use logo + abbreviation visuals")
print("- removed raw stack-ID caption from each lineup card")
print("- optimizer math unchanged")
