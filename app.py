from __future__ import annotations

import re
import pickle
import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

from datetime import datetime
from ui_theme import app_css
from ui_components import SENTIMENT_ORDER, SENTIMENT_UI, sentiment_display, player_visual_uri, validate_sentiment_ui_contract

from config import OptimizerSettings, discovery_example, raw_baseline
from data_loader import (
    join_projections,
    load_dk_salaries,
    load_projection_table,
)
from exporter import lineups_to_dk_dataframe
from optimizer import generate_lineups
from statrankings import load_snapshot
from portfolio import (
    allocate_three_contests,
    flex_distribution,
    lineup_table as _lineup_table,
    marginal_diversified_select,
    player_exposure,
    portfolio_summary,
    qb_exposure,
    repeated_cores,
    repeated_pairs,
    story_family_exposure as _story_family_exposure,
    team_skill_risk,
)


# Presentation helpers: never change lineup objects, settings, or export data.
DK_SLOT_ORDER = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "DST"]

PLAYER_SENTIMENT_OPTIONS = [
    "ADORE",
    "LOVE",
    "LIKE",
    "NEUTRAL",
    "DISLIKE",
    "HATE",
    "BAN",
]


def _set_sentiment(player_id, sentiment):
    controls = st.session_state.player_controls[player_id]
    controls["Sentiment"] = sentiment
    if sentiment == "BAN":
        controls["Exclude"] = True
    st.session_state.pool_editor_revision = st.session_state.get("pool_editor_revision", 0) + 1


def _reset_position_exposure(position, player_ids):
    for pid in player_ids:
        st.session_state.player_controls[pid]["Min %"] = 0
        st.session_state.player_controls[pid]["Max %"] = 100
    st.session_state[f"group_exposure_min_{position}"] = 0
    st.session_state[f"group_exposure_max_{position}"] = 100


def _set_visible_pool(key, player_ids):
    for pid in player_ids:
        controls = st.session_state.player_controls[pid]
        controls["Exclude"] = (
            not st.session_state[key] or controls.get("Sentiment") == "BAN"
        )


def _save_pool_edits(editor_key, player_ids):
    # Commit by DK ID before rebuilding the table; discard old row-index deltas.
    for row_index, changes in st.session_state[editor_key]["edited_rows"].items():
        controls = st.session_state.player_controls[player_ids[int(row_index)]]
        for column, value in changes.items():
            if column == "In Pool":
                controls["Exclude"] = not bool(value)
            elif column in ("Min %", "Max %"):
                controls[column] = int(value)
            elif column == "Sentiment":
                controls[column] = str(value).upper()
        if controls.get("Sentiment") == "BAN":
            controls["Exclude"] = True
    st.session_state.pool_editor_revision = st.session_state.get("pool_editor_revision", 0) + 1


def story_label(lineup):
    lookup = {player.dk_id: player.name for player in lineup.players}
    qb_id, receivers, bringbacks = lineup.story_signature()
    stack = " + ".join(lookup[player_id] for player_id in receivers) or "No pass catchers"
    opponents = " + ".join(lookup[player_id] for player_id in bringbacks) or "None"
    return f"{lookup[qb_id]} | Stack: {stack} | Bring-back: {opponents}"


def lineup_table(lineups):
    frame = _lineup_table(lineups).copy()
    if frame.empty:
        return frame
    frame["QBStory"] = [story_label(lineup) for lineup in lineups]
    columns = ["Lineup", *DK_SLOT_ORDER]
    return frame[columns + [column for column in frame.columns if column not in columns]]


def position_lineup_table(lineups, position):
    """Return a compact, read-only lineup view for one position group."""
    full = lineup_table(lineups).copy()
    if full.empty or position == "ALL":
        return full

    metadata = [
        column
        for column in (
            "Projection",
            "Salary",
            "SalaryLeft",
            "QBStory",
        )
        if column in full.columns
    ]

    if position == "QB":
        position_columns = ["QB"]
    elif position == "RB":
        position_columns = ["RB1", "RB2"]
        full["RB FLEX"] = [
            lineup.flex.name if lineup.flex.position == "RB" else "—"
            for lineup in lineups
        ]
        position_columns.append("RB FLEX")
    elif position == "WR":
        position_columns = ["WR1", "WR2", "WR3"]
        full["WR FLEX"] = [
            lineup.flex.name if lineup.flex.position == "WR" else "—"
            for lineup in lineups
        ]
        position_columns.append("WR FLEX")
    elif position == "TE":
        position_columns = ["TE"]
        full["TE FLEX"] = [
            lineup.flex.name if lineup.flex.position == "TE" else "—"
            for lineup in lineups
        ]
        position_columns.append("TE FLEX")
    elif position == "DST":
        position_columns = ["DST"]
    else:
        return full

    return full[["Lineup", *position_columns, *metadata]]


def story_family_exposure(lineups):
    frame = _story_family_exposure(lineups).copy()
    if not frame.empty:
        labels = {str(lineup.story_signature()): story_label(lineup) for lineup in lineups}
        frame["Signature"] = frame["Signature"].map(labels)
    return frame


def readable_label(label):
    overrides = {
        "QBStory": "QB / Stack Story",
        "Signature": "QB / Stack Story",
        "SalaryLeft": "Salary Remaining",
        "PlayerA": "Player A",
        "PlayerB": "Player B",
        "AnySkillLineupRate": "Lineups with Team Skill Players",
        "MultiSkillLineupRate": "Lineups with 2+ Team Skill Players",
        "Count": "Lineups",
        "Rate": "Portfolio Share",
        "Exposure": "Player Exposure",
        "Ownership": "Projected Ownership",
        "reason": "Reason / Hypothesis",
        "evidence_delta": "Evidence Delta",
        "counterargument": "Strongest Counterargument",
        "invalidation_trigger": "Invalidation Trigger",
    }
    if label in overrides:
        return overrides[label]
    if "_" in label:
        return label.replace("_", " ").title()
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label)


def show_table(frame, **kwargs):
    display = frame.copy()
    for column in ("Exposure", "Rate", "AnySkillLineupRate", "MultiSkillLineupRate"):
        if column in display.columns:
            display[column] = display[column].map(
                lambda value: "—" if pd.isna(value) else f"{value:.1%}"
            )
    display = display.rename(columns=readable_label)
    kwargs.setdefault("hide_index", True)
    return st.dataframe(display, **kwargs)


def show_portfolio_summary(summary):
    if not summary:
        st.info("No lineups selected.")
        return
    metrics = [
        ("Lineups", "lineups", ",.0f"),
        ("Average Projection", "mean_projection", ".2f"),
        ("Median Projection", "median_projection", ".2f"),
        ("90th Percentile Projection", "p90_projection", ".2f"),
        ("Highest Projection", "max_projection", ".2f"),
        ("Average Salary", "mean_salary", "$,.0f"),
        ("Average Salary Remaining", "mean_salary_left", "$,.0f"),
        ("Effective Player Count", "effective_player_count", ".1f"),
        ("Effective QB Count", "effective_qb_count", ".2f"),
        ("Average Shared Players", "mean_overlap", ".2f"),
        ("Most Shared Players", "max_overlap", ".0f"),
        ("90th Percentile Shared Players", "p90_overlap", ".2f"),
    ]
    for start in range(0, len(metrics), 4):
        columns = st.columns(4)
        for column, (label, key, spec) in zip(columns, metrics[start:start + 4]):
            value = summary.get(key)
            if value is None:
                formatted = "—"
            elif spec.startswith("$"):
                formatted = "$" + format(value, spec[1:])
            else:
                formatted = format(value, spec)
            column.metric(label, formatted)
    st.caption(
        "Effective counts describe concentration: greater concentration means a lower count. "
        "Shared players measures roster overlap between pairs of lineups."
    )

st.set_page_config(
    page_title="Draft Cave Optimizer",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

LOCAL_DK_FILE = DATA_DIR / "DKSalaries.csv"
LOCAL_PROJECTION_FILE = DATA_DIR / "projections.csv"
LOCAL_STATRANKINGS_FILE = DATA_DIR / "statrankings_week8.csv"
LAST_RUN_CACHE = DATA_DIR / ".draft_cave_last_run.pkl"


def _source_fingerprint(source):
    """Small source identity used only to guard restoring the last local run."""
    if isinstance(source, Path):
        stat = source.stat()
        return (str(source.resolve()), stat.st_size, stat.st_mtime_ns)

    name = getattr(source, "name", "uploaded")
    getvalue = getattr(source, "getvalue", None)
    if callable(getvalue):
        digest = hashlib.sha256(getvalue()).hexdigest()
        return (name, digest)

    return (name, None)


def _current_source_signature(dk_source, projection_source):
    sr_sig = None
    if LOCAL_STATRANKINGS_FILE.exists():
        sr_stat = LOCAL_STATRANKINGS_FILE.stat()
        sr_sig = (
            str(LOCAL_STATRANKINGS_FILE.resolve()),
            sr_stat.st_size,
            sr_stat.st_mtime_ns,
        )
    return {
        "dk": _source_fingerprint(dk_source),
        "projections": _source_fingerprint(projection_source),
        "statrankings": sr_sig,
    }


def _persist_last_run(result, settings, source_signature):
    """Persist the last successful reservoir; never regenerate implicitly."""
    try:
        LAST_RUN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with LAST_RUN_CACHE.open("wb") as handle:
            pickle.dump(
                {
                    "result": result,
                    "settings": settings,
                    "source_signature": source_signature,
                },
                handle,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
    except (OSError, pickle.PickleError):
        pass


def _restore_last_run(source_signature):
    if not LAST_RUN_CACHE.exists():
        return None
    try:
        with LAST_RUN_CACHE.open("rb") as handle:
            payload = pickle.load(handle)
    except (OSError, pickle.PickleError, EOFError, AttributeError):
        return None
    if payload.get("source_signature") != source_signature:
        return None
    return payload


def _clear_last_run_cache():
    try:
        LAST_RUN_CACHE.unlink(missing_ok=True)
    except OSError:
        pass


# ============================================================
# DRAFT CAVE UI
# ============================================================

st.markdown(app_css(), unsafe_allow_html=True)
validate_sentiment_ui_contract()

st.markdown(
    """
    <div class="dc-header">
        <div class="dc-brand">
            <div class="dc-logo">🏔️</div>
            <div>
                <div class="dc-brand-title">DRAFT CAVE</div>
                <div class="dc-brand-sub">BUILD • OPTIMIZE • WIN</div>
            </div>
        </div>
        <div class="dc-header-badge">
            NFL DFS OPTIMIZER • V2
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

if "intervention_log" not in st.session_state:
    st.session_state.intervention_log = []

if "player_controls" not in st.session_state:
    st.session_state.player_controls = {}

if "active_position" not in st.session_state:
    st.session_state.active_position = "ALL"


# ============================================================
# DATA SOURCES
# ============================================================

with st.expander("Slate Data", expanded=not (LOCAL_DK_FILE.exists() and LOCAL_PROJECTION_FILE.exists())):

    st.markdown(
        '<div class="dc-panel-title">Upload slate files</div>',
        unsafe_allow_html=True,
    )

    upload_left, upload_right = st.columns(2)

    with upload_left:
        dk_upload = st.file_uploader(
            "DraftKings Salary CSV",
            type=["csv"],
            key="dk_file",
        )

    with upload_right:
        projection_upload = st.file_uploader(
            "Projection CSV",
            type=["csv"],
            key="projection_file",
        )


if dk_upload is not None:
    dk_file = dk_upload
    dk_source_label = (
        f"Uploaded override: {dk_upload.name}"
    )

elif LOCAL_DK_FILE.exists():
    dk_file = LOCAL_DK_FILE
    dk_source_label = (
        f"Local file: {LOCAL_DK_FILE.name}"
    )

else:
    dk_file = None
    dk_source_label = "Missing"


if projection_upload is not None:
    projection_file = projection_upload
    projection_source_label = (
        f"Uploaded override: {projection_upload.name}"
    )

elif LOCAL_PROJECTION_FILE.exists():
    projection_file = LOCAL_PROJECTION_FILE
    projection_source_label = (
        f"Local file: {LOCAL_PROJECTION_FILE.name}"
    )

else:
    projection_file = None
    projection_source_label = "Missing"


if not dk_file or not projection_file:
    st.info(
        "Upload both the DraftKings salary CSV and projection CSV "
        "to begin, or place local files at:\n\n"
        f"- {LOCAL_DK_FILE}\n"
        f"- {LOCAL_PROJECTION_FILE}"
    )
    st.stop()


try:
    dk_players = load_dk_salaries(
        dk_file
    )

    projections = load_projection_table(
        projection_file
    )

    players, join_report = join_projections(
        dk_players,
        projections,
        source_name=projection_file.name,
    )

except Exception as exc:
    st.error(
        f"Input error: {exc}"
    )
    st.stop()


sr_snapshot = load_snapshot(LOCAL_STATRANKINGS_FILE, players)

current_source_signature = _current_source_signature(
    dk_file,
    projection_file,
)

if "generation_result" not in st.session_state:
    restored_run = _restore_last_run(current_source_signature)
    if restored_run is not None:
        st.session_state["generation_result"] = restored_run["result"]
        st.session_state["generation_settings"] = restored_run["settings"]
        st.session_state["generation_restored_from_cache"] = True


matched = (
    join_report["status"]
    .eq("MATCHED")
    .sum()
    if not join_report.empty
    else 0
)

unresolved = (
    join_report["status"]
    .eq("UNRESOLVED")
    .sum()
    if not join_report.empty
    else 0
)

with_projection = sum(
    p.projection is not None
    for p in players
)

ownership_complete = all(
    p.ownership is not None
    for p in players
    if p.projection is not None
)

ceiling_complete = all(
    p.ceiling is not None
    for p in players
    if p.projection is not None
)


# ============================================================
# SOURCE STATUS
# ============================================================

status_slot = st.empty()
local_times = [f.stat().st_mtime for f in (dk_file, projection_file) if isinstance(f, Path)]
freshness = datetime.fromtimestamp(min(local_times)).astimezone().strftime("%b %d %H:%M %Z") if len(local_times) == 2 else "Uploaded this session"
last_run_label = "Available" if "generation_result" in st.session_state else "Not run"
status_slot.caption(
    f"{'🟢' if not unresolved else '🟠'} {matched} matched · {unresolved} unresolved · "
    f"Oldest file update: {freshness} · Last run: {last_run_label} · "
    f"OWN: {'Complete' if ownership_complete else 'Missing'} · Ceiling: {'Complete' if ceiling_complete else 'Missing'}"
)
with st.expander("Data diagnostics", expanded=False):
    st.caption(f"Salary file: {dk_source_label} | Projections: {projection_source_label}")
    st.caption(f"StatRankings: {sr_snapshot.status} | {len(sr_snapshot.evidence_by_id)} matched · {len(sr_snapshot.unresolved)} unresolved")
    st.caption("File update time is not verification of projection or ownership freshness.")
if sr_snapshot.unresolved:
    with st.expander("Unresolved StatRankings evidence", expanded=False):
        st.dataframe(pd.DataFrame(sr_snapshot.unresolved), hide_index=True)


if unresolved:
    unresolved_df = join_report.loc[
        join_report["status"] == "UNRESOLVED"
    ]

    st.warning(
        f"{unresolved} projection row(s) did not resolve "
        "to a DraftKings player. No fuzzy auto-match was used."
    )

    with st.expander(
        "Unresolved identity rows",
        expanded=False,
    ):
        show_table(
            unresolved_df,
            width="stretch",
        )


# ============================================================
# PRESET
# ============================================================

preset_options = [
    "RAW BASELINE",
    "DISCOVERY",
    "CUSTOM",
]

preset = st.session_state.get(
    "optimizer_preset",
    "RAW BASELINE",
)

if preset not in preset_options:
    preset = "RAW BASELINE"


# ============================================================
# MAIN SETTINGS
# ============================================================

with st.container(border=True):

    st.markdown(
        '<div class="dc-panel-title">⚙️ Main Settings</div>',
        unsafe_allow_html=True,
    )

    settings_tabs = st.tabs(["Build", "Correlation", "Portfolio", "Advanced"])
    with settings_tabs[0]:
        settings_row = st.columns(
            [1.35, 1.1, 1.1, 1.2, 1.55]
        )

        with settings_row[0]:
            preset = st.selectbox(
                "Preset",
                options=preset_options,
                index=preset_options.index(
                    preset
                ),
                key="optimizer_preset",
            )

        if preset == "RAW BASELINE":
            settings = raw_baseline()

        elif preset == "DISCOVERY":
            settings = discovery_example()

        else:
            settings = OptimizerSettings()

        with settings_row[1]:
            settings.num_lineups = (
                st.number_input(
                    "Candidate Lineups",
                    min_value=1,
                    max_value=2000,
                    value=int(
                        settings.num_lineups
                    ),
                    step=1,
                )
            )

        with settings_row[2]:
            settings.minimum_uniques = (
                st.number_input(
                    "Minimum Uniques",
                    min_value=1,
                    max_value=9,
                    value=int(
                        settings.minimum_uniques
                    ),
                    step=1,
                )
            )

        with settings_row[3]:
            settings.minimum_salary = (
                st.number_input(
                    "Minimum Salary",
                    min_value=0,
                    max_value=50000,
                    value=int(
                        settings.minimum_salary
                    ),
                    step=100,
                )
            )

        with settings_row[4]:
            settings.randomization_pct = (
                st.slider(
                    "Randomization",
                    min_value=0,
                    max_value=50,
                    value=int(
                        round(
                            settings.randomization_pct
                            * 100
                        )
                    ),
                    step=1,
                    format="%d%%",
                )
                / 100.0
            )



    with settings_tabs[1]:
        st.markdown(
            '<div class="dc-section-label">'
            'Stacking & Correlation'
            '</div>',
            unsafe_allow_html=True,
        )

        correlation_row = st.columns(
            [1, 1, 1.15, 1.15, 1.35, 1.35]
        )

        with correlation_row[0]:
            settings.qb_stack_min = (
                st.number_input(
                    "QB Stack Min",
                    min_value=0,
                    max_value=4,
                    value=int(
                        settings.qb_stack_min
                    ),
                    step=1,
                )
            )

        with correlation_row[1]:
            settings.qb_stack_max = (
                st.number_input(
                    "QB Stack Max",
                    min_value=0,
                    max_value=4,
                    value=min(
                        int(
                            settings.qb_stack_max
                        ),
                        4,
                    ),
                    step=1,
                )
            )

        with correlation_row[2]:
            settings.require_bringback = (
                st.toggle(
                    "Require Bring-Back",
                    value=(
                        settings.require_bringback
                    ),
                )
            )

        with correlation_row[3]:
            settings.require_secondary_stack = (
                st.toggle(
                    "Secondary Stack",
                    value=(
                        settings.require_secondary_stack
                    ),
                )
            )

        with correlation_row[4]:
            settings.sim_same_team_pct = (
                st.slider(
                    "Same-Team SIM",
                    min_value=0,
                    max_value=50,
                    value=int(
                        round(
                            settings.sim_same_team_pct
                            * 100
                        )
                    ),
                    step=1,
                    format="%d%%",
                )
                / 100.0
            )

        with correlation_row[5]:
            settings.sim_opponent_pct = (
                st.slider(
                    "Opponent SIM",
                    min_value=0,
                    max_value=30,
                    value=int(
                        round(
                            settings.sim_opponent_pct
                            * 100
                        )
                    ),
                    step=1,
                    format="%d%%",
                )
                / 100.0
            )


    with settings_tabs[2]:
        # --------------------------------------------------------
        # PORTFOLIO CONTROLS
        # High-frequency controls stay visible instead of being buried.
        # --------------------------------------------------------

        st.markdown(
            '<div class="dc-section-label">Portfolio Controls</div>',
            unsafe_allow_html=True,
        )

        portfolio_controls = st.columns([2.2, 1, 1, 1])

        with portfolio_controls[0]:
            if ownership_complete:
                ownership_bounds = st.slider(
                    "Total Lineup Ownership",
                    min_value=0,
                    max_value=900,
                    value=(0, 900),
                    step=5,
                    format="%d%%",
                    help=(
                        "Cumulative projected ownership across all nine lineup slots. "
                        "Leave at the full range to keep the constraint off."
                    ),
                    key="total_lineup_ownership_range_v3",
                )
                if ownership_bounds != (0, 900):
                    settings.ownership_min = float(ownership_bounds[0])
                    settings.ownership_max = float(ownership_bounds[1])
            else:
                st.slider(
                    "Total Lineup Ownership",
                    min_value=0,
                    max_value=900,
                    value=(0, 900),
                    step=5,
                    format="%d%%",
                    disabled=True,
                    help="Projected ownership is not available in the current projection source.",
                    key="total_lineup_ownership_unavailable_v3",
                )
                st.caption("Waiting for projected ownership data.")

        for column, position in zip(portfolio_controls[1:], ["RB", "WR", "TE"]):
            with column:
                flex_pct = st.number_input(
                    f"{position} FLEX Max %",
                    min_value=0,
                    max_value=100,
                    value=int(settings.flex_position_caps[position] * 100),
                    step=5,
                    key=f"flex_cap_{position.lower()}_v3",
                )
                settings.flex_position_caps[position] = float(flex_pct) / 100.0

    # --------------------------------------------------------
    # CONSTRUCTION RULES / DIAGNOSTICS
    # Lower-frequency controls are compact and kept out of the main canvas.
    # --------------------------------------------------------

    settings.statrankings_edge_by_id = sr_snapshot.edge_by_id

    with settings_tabs[3]:
        with st.expander(
            "Construction Rules & Diagnostics",
            expanded=False,
        ):
            construction_cols = st.columns([1.25, 1, 1.7, 1.45, 1.45])

            with construction_cols[0]:
                settings.statrankings_influence = st.selectbox(
                    "StatRankings Influence",
                    options=["OFF", "LOW", "MEDIUM", "HIGH"],
                    index=0,
                    help=(
                        "LOW max ±0.5%, MEDIUM ±1.0%, HIGH ±2.0%; "
                        "objective only, never stored projection."
                    ),
                    key="sr_influence_v3",
                )

            with construction_cols[1]:
                settings.random_seed = st.number_input(
                    "Random Seed",
                    min_value=0,
                    max_value=999999,
                    value=int(settings.random_seed),
                    step=1,
                    help="Only matters when Randomization is above 0%.",
                    key="random_seed_v3",
                )

            with construction_cols[2]:
                offense_vs_dst = st.selectbox(
                    "Max offense vs opposing DST",
                    options=["OFF", 0, 1, 2, 3, 4, 5, 6, 7, 8],
                    key="offense_vs_dst_v3",
                )
                if offense_vs_dst != "OFF":
                    settings.max_offense_vs_opposing_dst = int(offense_vs_dst)

            with construction_cols[3]:
                qb_rb = st.selectbox(
                    "Max same-team RB with QB",
                    options=["OFF", 0, 1, 2, 3],
                    key="qb_rb_v3",
                )
                if qb_rb != "OFF":
                    settings.max_qb_with_same_team_rb = int(qb_rb)

            with construction_cols[4]:
                qb_dst = st.selectbox(
                    "Max same-team DST with QB",
                    options=["OFF", 0, 1],
                    key="qb_dst_v3",
                )
                if qb_dst != "OFF":
                    settings.max_qb_with_same_team_dst = int(qb_dst)

        # Position Exposure Caps are intentionally not exposed here anymore.
        # The optimizer capability remains available in config.py, but the UI now
        # uses the Player Pool position-tab group Min/Max controls for exposure work.

        with st.expander(
            "Decision / Intervention Log",
            expanded=False,
        ):
            intervention_cols = st.columns(4)

            with intervention_cols[0]:
                reason = st.text_input("Reason / hypothesis")

            with intervention_cols[1]:
                evidence = st.text_input("Evidence delta")

            with intervention_cols[2]:
                counterargument = st.text_input("Strongest counterargument")

            with intervention_cols[3]:
                invalidation = st.text_input("Invalidation trigger")

            log_left, reset_right = st.columns([1, 1])

            with log_left:
                if st.button(
                    "Log Intervention",
                    width="stretch",
                ):
                    st.session_state.intervention_log.append(
                        {
                            "reason": reason,
                            "evidence_delta": evidence,
                            "counterargument": counterargument,
                            "invalidation_trigger": invalidation,
                        }
                    )

            with reset_right:
                if st.button(
                    "Reset Instructions",
                    width="stretch",
                ):
                    st.info("Select RAW BASELINE above before regenerating.")

            if st.session_state.intervention_log:
                show_table(
                    pd.DataFrame(st.session_state.intervention_log),
                    width="stretch",
                    hide_index=True,
                )


# ============================================================
# PLAYER DATA
# ============================================================

available = [
    p
    for p in players
    if p.projection is not None
]

missing_projection_players = [
    p
    for p in players
    if p.projection is None
]


current_player_ids = {
    int(p.dk_id)
    for p in available
}


for p in available:

    dk_id = int(
        p.dk_id
    )

    if dk_id not in (
        st.session_state.player_controls
    ):
        st.session_state.player_controls[
            dk_id
        ] = {
            "Lock": False,
            "Exclude": False,
            "Min %": 0,
            "Max %": 100,
            "Sentiment": "NEUTRAL",
        }

    # Migration-safe defaults for sessions created before these controls existed.
    st.session_state.player_controls[dk_id].setdefault("Lock", False)
    st.session_state.player_controls[dk_id].setdefault("Exclude", False)
    st.session_state.player_controls[dk_id].setdefault("Min %", 0)
    st.session_state.player_controls[dk_id].setdefault("Max %", 100)
    st.session_state.player_controls[dk_id].setdefault("Sentiment", "NEUTRAL")


st.session_state.player_controls = {
    dk_id: controls
    for dk_id, controls
    in st.session_state.player_controls.items()
    if dk_id in current_player_ids
}


# ============================================================
# PLAYER POOL
# ============================================================

with st.container(border=True):

    player_header_left, player_header_right = (
        st.columns([4, 1])
    )

    with player_header_left:
        st.markdown(
            f"""
            <div class="dc-panel-title">
                👥 Player Pool
                <span class="dc-muted">
                    ({len(available)} eligible)
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with player_header_right:
        if st.button(
            "Reset Filters",
            width="stretch",
        ):
            st.session_state.active_position = "ALL"
            st.session_state.player_search_v2 = ""
            st.session_state.player_team_filter_v2 = []
            st.session_state.player_opp_filter_v2 = []
            st.rerun()


    # --------------------------------------------------------
    # POSITION BUTTON BAR
    # --------------------------------------------------------

    active_position = st.radio(
        "Position",
        options=[
            "ALL",
            "QB",
            "RB",
            "WR",
            "TE",
            "DST",
        ],
        horizontal=True,
        key="active_position",
        label_visibility="collapsed",
    )

    # --------------------------------------------------------
    # POSITION-WIDE EXPOSURE CONTROLS
    # The active position tab is the bulk-edit target. There is
    # deliberately no second position selector.
    # --------------------------------------------------------

    if active_position in {"QB", "RB", "WR", "TE", "DST"}:
        position_players = [
            player
            for player in available
            if player.position == active_position
        ]

        # Default the compact controls to the common value currently used by
        # the active position. If players already have mixed overrides, show
        # neutral defaults (0/100) until the user explicitly applies a group
        # value. Individual row overrides remain untouched until Apply.
        current_mins = {
            int(st.session_state.player_controls[int(player.dk_id)]["Min %"])
            for player in position_players
        }
        current_maxes = {
            int(st.session_state.player_controls[int(player.dk_id)]["Max %"])
            for player in position_players
        }

        default_group_min = next(iter(current_mins)) if len(current_mins) == 1 else 0
        default_group_max = next(iter(current_maxes)) if len(current_maxes) == 1 else 100

        group_cols = st.columns([1.2, 0.8, 0.8, 0.95, 0.95, 3.4])

        with group_cols[0]:
            st.markdown(
                f"**{active_position} group exposure**"
            )
            st.caption(f"Applies to all {len(position_players)} {active_position} players")

        with group_cols[1]:
            group_min = st.number_input(
                f"{active_position} Min %",
                min_value=0,
                max_value=100,
                value=int(default_group_min),
                step=5,
                key=f"group_exposure_min_{active_position}",
            )

        with group_cols[2]:
            group_max = st.number_input(
                f"{active_position} Max %",
                min_value=0,
                max_value=100,
                value=int(default_group_max),
                step=5,
                key=f"group_exposure_max_{active_position}",
            )

        with group_cols[3]:
            st.write("")
            apply_group_exposure = st.button(
                "Apply",
                width="stretch",
                key=f"apply_group_exposure_{active_position}",
            )

        with group_cols[4]:
            st.write("")
            reset_group_exposure = st.button(
                "Reset",
                width="stretch",
                key=f"reset_group_exposure_{active_position}",
                on_click=_reset_position_exposure,
                args=(active_position, [int(p.dk_id) for p in position_players]),
            )

        if apply_group_exposure:
            if int(group_min) > int(group_max):
                st.error("Position minimum exposure cannot exceed maximum exposure.")
            else:
                for player in position_players:
                    controls = st.session_state.player_controls[int(player.dk_id)]
                    controls["Min %"] = int(group_min)
                    controls["Max %"] = int(group_max)

                st.success(
                    f"Applied {active_position} Min {int(group_min)}% / "
                    f"Max {int(group_max)}% to {len(position_players)} players."
                )
                st.rerun()


    else:
        st.caption(
            "Select QB, RB, WR, TE, or DST above to set Min/Max exposure "
            "for that entire position group."
        )


    # --------------------------------------------------------
    # QUICK FILTERS
    # --------------------------------------------------------

    teams = sorted(
        {
            str(p.team)
            for p in available
        }
    )

    opponents = sorted(
        {
            str(p.opponent)
            for p in available
        }
    )

    filter_cols = st.columns(
        [2.15, 1.15, 1.15, 1.3, 1.3, 1.3]
    )

    with filter_cols[0]:
        player_search = st.text_input(
            "Search",
            placeholder=(
                "Search player, team or opponent..."
            ),
            key="player_search_v2",
            label_visibility="collapsed",
        )

    with filter_cols[1]:
        selected_teams = st.multiselect(
            "Team",
            options=teams,
            default=[],
            key="player_team_filter_v2",
            placeholder="Team",
        )

    with filter_cols[2]:
        selected_opponents = st.multiselect(
            "Opponent",
            options=opponents,
            default=[],
            key="player_opp_filter_v2",
            placeholder="Opponent",
        )

    salary_values = [
        int(p.salary)
        for p in available
    ]

    min_salary_available = (
        min(salary_values)
        if salary_values
        else 0
    )

    max_salary_available = (
        max(salary_values)
        if salary_values
        else 50000
    )

    with filter_cols[3]:
        salary_range = st.slider(
            "Salary Range",
            min_value=min_salary_available,
            max_value=max_salary_available,
            value=(
                min_salary_available,
                max_salary_available,
            ),
            step=100,
        )


    projection_values = [
        float(p.projection)
        for p in available
        if p.projection is not None
    ]

    min_projection_available = (
        float(
            min(projection_values)
        )
        if projection_values
        else 0.0
    )

    max_projection_available = (
        float(
            max(projection_values)
        )
        if projection_values
        else 1.0
    )

    with filter_cols[4]:
        projection_range = st.slider(
            "Projection Range",
            min_value=float(
                min_projection_available
            ),
            max_value=float(
                max_projection_available
            ),
            value=(
                float(
                    min_projection_available
                ),
                float(
                    max_projection_available
                ),
            ),
            step=0.5,
        )


    with filter_cols[5]:

        if ownership_complete:

            ownership_values = [
                float(p.ownership)
                for p in available
                if p.ownership is not None
            ]

            own_min_available = (
                float(
                    min(ownership_values)
                )
                if ownership_values
                else 0.0
            )

            own_max_available = (
                float(
                    max(ownership_values)
                )
                if ownership_values
                else 100.0
            )

            ownership_range = st.slider(
                "Ownership Range",
                min_value=float(
                    own_min_available
                ),
                max_value=float(
                    own_max_available
                ),
                value=(
                    float(
                        own_min_available
                    ),
                    float(
                        own_max_available
                    ),
                ),
                step=0.5,
            )

        else:

            ownership_range = None

            st.caption(
                "Ownership\nUnavailable"
            )


    # --------------------------------------------------------
    # FILTER PLAYER LIST
    # --------------------------------------------------------

    filtered_players = []

    search_text = (
        player_search
        .strip()
        .lower()
    )

    for p in available:

        if (
            active_position != "ALL"
            and p.position != active_position
        ):
            continue

        if search_text:

            searchable = (
                f"{p.name} "
                f"{p.team} "
                f"{p.opponent}"
            ).lower()

            if search_text not in searchable:
                continue

        if (
            selected_teams
            and p.team not in selected_teams
        ):
            continue

        if (
            selected_opponents
            and p.opponent
            not in selected_opponents
        ):
            continue

        if not (
            salary_range[0]
            <= int(p.salary)
            <= salary_range[1]
        ):
            continue

        if not (
            projection_range[0]
            <= float(p.projection)
            <= projection_range[1]
        ):
            continue

        if (
            ownership_range is not None
            and p.ownership is not None
            and not (
                ownership_range[0]
                <= float(p.ownership)
                <= ownership_range[1]
            )
        ):
            continue

        filtered_players.append(
            p
        )


    st.caption(
        f"Showing {len(filtered_players)} of "
        f"{len(available)} optimizer-eligible players."
    )

    # Preserve Lock capability without a second checkbox column.
    # In Pool is the only checkbox column in the player table.
    player_by_id = {int(player.dk_id): player for player in available}
    current_locked_ids = sorted(
        dk_id
        for dk_id, controls in st.session_state.player_controls.items()
        if controls.get("Lock", False) and dk_id in player_by_id
    )

    selected_locked_ids = st.multiselect(
        "Locked players",
        options=sorted(player_by_id),
        default=current_locked_ids,
        format_func=lambda pid: (
            f"{player_by_id[pid].name} — "
            f"{player_by_id[pid].team} {player_by_id[pid].position}"
        ),
        help="Optional. Locked players are forced into every generated lineup.",
        placeholder="No players locked",
        key="locked_players_multiselect_v5",
    )

    selected_locked_ids = {int(pid) for pid in selected_locked_ids}
    for dk_id, controls in st.session_state.player_controls.items():
        controls["Lock"] = dk_id in selected_locked_ids

    # DS-style header checkbox: select/deselect every currently shown player.
    visible_ids = [int(player.dk_id) for player in filtered_players]
    all_visible_in_pool = bool(visible_ids) and all(
        not st.session_state.player_controls[dk_id].get("Exclude", False)
        for dk_id in visible_ids
    )

    select_all_key = f"in_pool_all_{active_position}"
    st.session_state[select_all_key] = all_visible_in_pool
    st.checkbox(
        "In Pool",
        key=select_all_key,
        help="Select or deselect every player currently shown below. BAN remains excluded.",
        on_change=_set_visible_pool,
        args=(select_all_key, visible_ids),
    )


    # --------------------------------------------------------
    # PLAYER TABLE
    # --------------------------------------------------------

    if filtered_players:
        sentiment_players = {int(p.dk_id): p for p in filtered_players}
        sentiment_cols = st.columns([3, 5])
        with sentiment_cols[0]:
            sentiment_id = st.selectbox(
                "Sentiment player", list(sentiment_players),
                format_func=lambda pid: f"{sentiment_players[pid].name} · {sentiment_players[pid].team} · DK {pid}",
                key="sentiment_player",
            )
        with sentiment_cols[1]:
            st.caption("Sentiment · objective only; projection unchanged")
            for col, state in zip(st.columns(7), SENTIMENT_ORDER):
                col.button(
                    SENTIMENT_UI[state]["icon"],
                    help=sentiment_display(state) + " · " + {"ADORE": "+10%", "LOVE": "+7.5%", "LIKE": "+5%", "NEUTRAL": "0%", "DISLIKE": "−5%", "HATE": "−10%", "BAN": "exclude"}[state],
                    key=f"sentiment_{state}",
                    type="primary" if st.session_state.player_controls[sentiment_id]["Sentiment"] == state else "secondary",
                    on_click=_set_sentiment, args=(sentiment_id, state), width="stretch",
                )
    show_research = st.checkbox("Show research columns", value=False)

    pool_rows = []

    for p in filtered_players:

        controls = (
            st.session_state.player_controls[
                int(p.dk_id)
            ]
        )

        value_score = None

        if (
            p.projection is not None
            and p.salary
        ):
            value_score = (
                float(p.projection)
                / float(p.salary)
                * 1000.0
            )

        pool_rows.append(
            {
                "In Pool": not controls[
                    "Exclude"
                ],
                "Min %": controls[
                    "Min %"
                ],
                "Max %": controls[
                    "Max %"
                ],
                "Sentiment": controls.get(
                    "Sentiment",
                    "NEUTRAL",
                ),
                "ID": p.dk_id,
                "Player": p.name,
                "Visual": player_visual_uri(p, BASE_DIR / "assets"),
                "Conviction": sentiment_display(controls.get("Sentiment", "NEUTRAL")),
                "Team": p.team,
                "Opp": p.opponent,
                "Pos": p.position,
                "Salary": p.salary,
                "Proj": p.projection,
                "Own %": "—" if p.ownership is None else f"{p.ownership:.1f}",
                "Value": value_score,
                "Ceiling": "—" if p.ceiling is None else f"{p.ceiling:.2f}",
                "Role": sr_snapshot.evidence_by_id.get(p.dk_id, {}).get("Role_Score"),
                "Form": sr_snapshot.evidence_by_id.get(p.dk_id, {}).get("Form_Score"),
                "Matchup": sr_snapshot.evidence_by_id.get(p.dk_id, {}).get("Matchup_Score"),
                "Env": sr_snapshot.evidence_by_id.get(p.dk_id, {}).get("Environment_Score"),
                "Edge": sr_snapshot.evidence_by_id.get(p.dk_id, {}).get("Edge_Score"),
                "Injury": None,
                "Status": p.status,
            }
        )


    pool_df = pd.DataFrame(pool_rows, columns=[
        "In Pool", "Visual", "Player", "Team", "Opp", "Pos", "Salary", "Proj",
        "Own %", "Ceiling", "Value", "Conviction", "Min %", "Max %", "ID",
        "Sentiment", "Role", "Form", "Matchup", "Env", "Edge", "Injury", "Status",
    ])
    display_columns = ["In Pool", "Visual", "Player", "Team", "Opp", "Pos", "Salary",
                       "Proj", "Own %", "Ceiling", "Value", "Conviction", "Min %", "Max %"]
    if show_research:
        display_columns += ["ID", "Role", "Form", "Matchup", "Env", "Edge", "Injury", "Status"]

    editor_key = f"player_pool_editor_v5_{st.session_state.get('pool_editor_revision', 0)}"
    edited_pool_df = st.data_editor(
        pool_df,
        width="stretch",
        height=455,
        row_height=28,
        column_order=display_columns,
        hide_index=True,
        disabled=[
            "Visual", "Conviction", "Sentiment",
            "ID",
            "Player",
            "Team",
            "Opp",
            "Pos",
            "Salary",
            "Proj",
            "Own %",
            "Value",
            "Ceiling",
            "Role",
            "Form",
            "Matchup",
            "Env",
            "Edge",
            "Injury",
            "Status",
        ],
        column_config={

            "In Pool": (
                st.column_config.CheckboxColumn(
                    "In Pool",
                    help=(
                        "Checked = eligible for optimizer. "
                        "Uncheck to remove the player from the pool."
                    ),
                    default=True,
                )
            ),

            "Sentiment": None,
            "Visual": st.column_config.ImageColumn("", width=35),
            "Player": st.column_config.TextColumn("Player", width="medium"),
            "Conviction": st.column_config.TextColumn("Sentiment", width="small"),
            "Min %": (
                st.column_config.NumberColumn(
                    "Min %",
                    min_value=0,
                    max_value=100,
                    step=5,
                    format="%d%%",
                )
            ),

            "Max %": (
                st.column_config.NumberColumn(
                    "Max %",
                    min_value=0,
                    max_value=100,
                    step=5,
                    format="%d%%",
                )
            ),

            "ID": (
                st.column_config.NumberColumn(
                    "DK ID",
                    format="%d",
                )
            ),

            "Salary": (
                st.column_config.NumberColumn(
                    "Salary",
                    format="$%d",
                )
            ),

            "Proj": (
                st.column_config.NumberColumn(
                    "Proj",
                    format="%.2f",
                )
            ),

            "Own %": st.column_config.TextColumn("Own %", width="small"),

            "Value": (
                st.column_config.NumberColumn(
                    "Value",
                    format="%.2f",
                    help=(
                        "Projection points per "
                        "$1,000 salary."
                    ),
                )
            ),

            "Ceiling": st.column_config.TextColumn("Ceiling", width="small"),

            "Role": st.column_config.NumberColumn("Role", format="%.2f"),
            "Form": st.column_config.NumberColumn("Form", format="%.2f"),
            "Matchup": st.column_config.NumberColumn("Matchup", format="%.2f"),
            "Env": st.column_config.NumberColumn("Env", format="%.2f"),
            "Edge": st.column_config.NumberColumn("Edge", format="%.2f"),
        },
        key=editor_key,
        on_change=_save_pool_edits,
        args=(editor_key, visible_ids),
    )


    with st.expander("StatRankings evidence details", expanded=False):
        detail_players = {p.dk_id: p for p in filtered_players}
        if detail_players:
            detail_id = st.selectbox(
                "Evidence player", options=list(detail_players),
                format_func=lambda pid: f"{detail_players[pid].name} — {detail_players[pid].team} {detail_players[pid].position} ({pid})",
            )
            evidence = sr_snapshot.evidence_by_id.get(detail_id)
            if evidence is None:
                st.caption("No resolved StatRankings evidence for this player.")
            else:
                for label, field in (
                    ("SR as-of", "SR_AsOf"), ("DK FP/G", "DK_FPPG"),
                    ("DK FP/G L5", "DK_FPPG_L5"), ("Role reason", "Role_Reason"),
                    ("Form reason", "Form_Reason"), ("Matchup reason", "Matchup_Reason"),
                    ("Environment reason", "Environment_Reason"),
                ):
                    value = evidence.get(field)
                    st.text(f"{label}: {value if value is not None else '—'}")
        else:
            st.caption("No players match the current filters.")


# ============================================================
# SAVE PLAYER CONTROL STATE
# ============================================================

for _, row in edited_pool_df.iterrows():

    dk_id = int(
        row["ID"]
    )

    existing_controls = st.session_state.player_controls[dk_id]
    sentiment = str(row["Sentiment"]).upper()

    st.session_state.player_controls[
        dk_id
    ] = {
        "Lock": bool(existing_controls.get("Lock", False)),
        "Exclude": not bool(row["In Pool"]),
        "Min %": int(row["Min %"]),
        "Max %": int(row["Max %"]),
        "Sentiment": sentiment,
    }

    # BAN is an explicit pool removal instruction.
    if sentiment == "BAN":
        st.session_state.player_controls[dk_id]["Exclude"] = True


locked_ids = {
    dk_id
    for dk_id, controls
    in st.session_state.player_controls.items()
    if controls["Lock"]
}

excluded_ids = {
    dk_id
    for dk_id, controls
    in st.session_state.player_controls.items()
    if controls["Exclude"]
}


lock_exclude_conflicts = (
    locked_ids
    & excluded_ids
)


if lock_exclude_conflicts:

    player_name_by_id = {
        int(p.dk_id): p.name
        for p in available
    }

    conflict_names = [
        player_name_by_id[
            dk_id
        ]
        for dk_id in sorted(
            lock_exclude_conflicts
        )
    ]

    st.error(
        "A player cannot be both locked and excluded: "
        + ", ".join(
            conflict_names
        )
    )

    st.stop()


exposure_conflict_ids = {
    dk_id
    for dk_id, controls
    in st.session_state.player_controls.items()
    if (
        controls["Min %"]
        > controls["Max %"]
    )
}


if exposure_conflict_ids:

    player_name_by_id = {
        int(p.dk_id): p.name
        for p in available
    }

    conflict_names = [
        player_name_by_id[
            dk_id
        ]
        for dk_id in sorted(
            exposure_conflict_ids
        )
    ]

    st.error(
        "Minimum exposure cannot exceed "
        "maximum exposure: "
        + ", ".join(
            conflict_names
        )
    )

    st.stop()


settings.lock_players = (
    locked_ids
)

settings.exclude_players = (
    excluded_ids
)

settings.player_min_exposure = {}

settings.player_max_exposure = {}


for dk_id, controls in (
    st.session_state.player_controls.items()
):

    min_pct = float(
        controls["Min %"]
    )

    max_pct = float(
        controls["Max %"]
    )

    if min_pct > 0:

        settings.player_min_exposure[
            dk_id
        ] = (
            min_pct
            / 100.0
        )

    if max_pct < 100:

        settings.player_max_exposure[
            dk_id
        ] = (
            max_pct
            / 100.0
        )


settings.player_sentiment_by_id = {
    int(dk_id): str(controls.get("Sentiment", "NEUTRAL")).upper()
    for dk_id, controls in st.session_state.player_controls.items()
    if str(controls.get("Sentiment", "NEUTRAL")).upper() != "NEUTRAL"
}


# ============================================================
# PLAYER CONTROL SUMMARY
# ============================================================

control_cols = st.columns(4)

control_cols[0].metric(
    "Locked",
    len(
        settings.lock_players
    ),
)

control_cols[1].metric(
    "Excluded",
    len(
        settings.exclude_players
    ),
)

control_cols[2].metric(
    "Exposure Overrides",
    len(
        set(
            settings.player_min_exposure
        )
        | set(
            settings.player_max_exposure
        )
    ),
)

control_cols[3].metric(
    "Projection Coverage",
    f"{with_projection}/{len(players)}",
)


if missing_projection_players:

    missing_names = ", ".join(
        p.name
        for p in missing_projection_players
    )

    st.warning(
        f"{len(missing_projection_players)} player(s) "
        "have a missing projection and are unavailable "
        f"for optimizer controls: {missing_names}"
    )


# ============================================================
# GENERATE
# ============================================================

with st.container(key="generate_action"):

    st.write("")

    generate_clicked = st.button(
        f"GENERATE {settings.num_lineups} LINEUPS",
        type="primary",
        width="stretch",
    )

    clear_results_clicked = st.button(
        "Clear Generated Results",
        width="stretch",
    )


if clear_results_clicked:
    for key in (
        "generation_result",
        "generation_settings",
        "generation_restored_from_cache",
        "selected_lineups",
        "contest_allocations",
    ):
        st.session_state.pop(key, None)
    _clear_last_run_cache()
    st.rerun()


if generate_clicked:

    try:

        with st.spinner(
            "Generating candidate lineups..."
        ):

            result = generate_lineups(
                players,
                settings,
            )

        st.session_state[
            "generation_result"
        ] = result

        st.session_state[
            "generation_settings"
        ] = settings

        st.session_state["generation_restored_from_cache"] = False
        st.session_state.pop("selected_lineups", None)
        st.session_state.pop("contest_allocations", None)
        _persist_last_run(
            result,
            settings,
            current_source_signature,
        )

    except Exception as exc:

        st.error(
            f"Generation error: {exc}"
        )


# ============================================================
# NO GENERATED RESERVOIR YET
# ============================================================

if (
    "generation_result"
    not in st.session_state
):

    st.info(
        "Configure the slate above, review the Player Pool, "
        "then click Generate Lineups."
    )

    st.stop()


result = st.session_state[
    "generation_result"
]

generated_settings = st.session_state.get("generation_settings")
if generated_settings is not None and settings != generated_settings:
    st.warning(
        "Settings changed since the last generation. The lineups below are "
        "still the previous build; click Generate Lineups to replace them."
    )
elif st.session_state.get("generation_restored_from_cache"):
    st.info(
        "Restored the last successful generated reservoir from this slate. "
        "No lineups were regenerated."
    )

lineups = result.lineups


if result.warnings:

    for warning in result.warnings:
        st.warning(
            warning
        )


if not lineups:

    st.error(
        "No legal lineups were generated."
    )

    st.stop()


# ============================================================
# CANDIDATE RESERVOIR
# ============================================================

summary = portfolio_summary(
    lineups
)


with st.container(border=True):

    st.markdown(
        f"""
        <div class="dc-panel-title">
            🧮 Generated Lineups
            <span class="dc-muted">
                ({len(lineups)})
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    reservoir_metrics = st.columns(5)

    reservoir_metrics[0].metric(
        "Generated",
        len(lineups),
    )

    reservoir_metrics[1].metric(
        "Mean Projection",
        f"{summary['mean_projection']:.2f}",
    )

    reservoir_metrics[2].metric(
        "Effective Players",
        f"{summary['effective_player_count']:.1f}",
    )

    reservoir_metrics[3].metric(
        "Effective QBs",
        f"{summary['effective_qb_count']:.2f}",
    )

    reservoir_metrics[4].metric(
        "Mean Overlap",
        f"{summary['mean_overlap']:.2f}",
    )


    tabs = st.tabs(
        [
            "Lineups",
            "Exposure",
            "Stacks & Games",
            "Portfolio Risk",
            "Repetition",
            "Export",
        ]
    )


    # --------------------------------------------------------
    # LINEUPS
    # --------------------------------------------------------

    with tabs[0]:

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


    # --------------------------------------------------------
    # STACK ANALYSIS
    # --------------------------------------------------------

    with tabs[4]:

        stack_left, stack_right = (
            st.columns(2)
        )

        with stack_left:

            st.markdown(
                "### Repeated Pairs"
            )

            show_table(
                repeated_pairs(
                    lineups,
                    top_n=30,
                ),
                width="stretch",
            )

        with stack_right:

            st.markdown(
                "### Repeated 3-Man Cores"
            )

            show_table(
                repeated_cores(
                    lineups,
                    core_size=3,
                    top_n=30,
                ),
                width="stretch",
            )


    # --------------------------------------------------------
    # PORTFOLIO
    # --------------------------------------------------------

    with tabs[3]:

        st.markdown(
            "### Portfolio Summary"
        )

        show_portfolio_summary(
            summary
        )

        st.markdown(
            "### Team Skill Risk"
        )

        show_table(
            team_skill_risk(
                lineups
            ),
            width="stretch",
        )


    # --------------------------------------------------------
    # STORIES
    # --------------------------------------------------------

    with tabs[2]:

        st.markdown(
            "### QB / Game / Stack Story Families"
        )

        st.caption(
            "Ticket uniqueness and story uniqueness "
            "are not the same thing."
        )

        show_table(
            story_family_exposure(
                lineups
            ),
            width="stretch",
        )


    # --------------------------------------------------------
    # FINAL SELECTION
    # --------------------------------------------------------

    with tabs[3]:

        st.markdown(
            "### Outcome-Blind Final Selection"
        )

        final_controls = st.columns(
            [1, 1, 1]
        )

        with final_controls[0]:

            target = st.number_input(
                "Final Portfolio Size",
                min_value=1,
                max_value=len(
                    lineups
                ),
                value=min(
                    20,
                    len(
                        lineups
                    ),
                ),
                step=1,
            )

        with final_controls[1]:

            overlap_penalty = (
                st.slider(
                    "Overlap Penalty",
                    min_value=0.0,
                    max_value=5.0,
                    value=2.0,
                    step=0.1,
                )
            )

        with final_controls[2]:

            story_penalty = (
                st.slider(
                    "Story-Family Penalty",
                    min_value=0.0,
                    max_value=5.0,
                    value=1.0,
                    step=0.1,
                )
            )


        if st.button(
            "Select Final Portfolio",
            width="stretch",
        ):

            selected = (
                marginal_diversified_select(
                    lineups,
                    target=int(
                        target
                    ),
                    overlap_penalty=float(
                        overlap_penalty
                    ),
                    story_penalty=float(
                        story_penalty
                    ),
                )
            )

            st.session_state[
                "selected_lineups"
            ] = selected


        selected = (
            st.session_state.get(
                "selected_lineups"
            )
        )


        if selected:

            show_table(
                lineup_table(
                    selected
                ),
                width="stretch",
            )

            st.markdown(
                "#### Selected Portfolio Summary"
            )

            show_portfolio_summary(
                portfolio_summary(
                    selected
                )
            )


        if len(lineups) == 60:

            st.divider()

            st.markdown(
                "### Recurring 3×20 Contest Allocation"
            )

            st.caption(
                "Provisional balanced allocator for "
                "First Down, Quarter Jukebox, and "
                "Dime Package."
            )

            if st.button(
                "Allocate 60 Across 3×20"
            ):

                allocations = (
                    allocate_three_contests(
                        lineups
                    )
                )

                st.session_state[
                    "contest_allocations"
                ] = allocations


            allocations = (
                st.session_state.get(
                    "contest_allocations"
                )
            )


            if allocations:

                for (
                    name,
                    contest_lineups,
                ) in allocations.items():

                    with st.expander(
                        name,
                        expanded=False,
                    ):

                        show_table(
                            lineup_table(
                                contest_lineups
                            ),
                            width="stretch",
                        )


    # --------------------------------------------------------
    # EXPORT
    # --------------------------------------------------------

    with tabs[5]:

        st.markdown(
            "### DraftKings Export"
        )

        export_source = st.radio(
            "Export Source",
            [
                "Candidate Reservoir",
                "Selected Final Portfolio",
            ],
            horizontal=True,
        )


        if (
            export_source
            == "Selected Final Portfolio"
        ):

            export_lineups = (
                st.session_state.get(
                    "selected_lineups"
                )
            )

            if not export_lineups:

                st.warning(
                    "No final portfolio has been "
                    "selected yet."
                )

                export_lineups = []

        else:

            export_lineups = (
                lineups
            )


        if export_lineups:

            export_df = (
                lineups_to_dk_dataframe(
                    export_lineups
                )
            )

            display_df = lineup_table(export_lineups)[DK_SLOT_ORDER]

            show_table(
                display_df,
                width="stretch",
            )

            csv_bytes = (
                export_df
                .to_csv(
                    index=False
                )
                .encode(
                    "utf-8"
                )
            )

            st.download_button(
                "⬇ Download DraftKings CSV",
                data=csv_bytes,
                file_name=(
                    "draft_cave_lineups.csv"
                ),
                mime="text/csv",
                width="stretch",
            )


        st.divider()

        with st.expander("Generation Details", expanded=False):
            detail_columns = st.columns(3)
            detail_columns[0].metric("Candidate Lineups", len(lineups))
            detail_columns[1].metric("Warnings", len(result.warnings))
            detail_columns[2].metric(
                "Logged Interventions", len(st.session_state.intervention_log)
            )
            for warning in result.warnings:
                st.warning(warning)
            if st.session_state.intervention_log:
                st.markdown("**Intervention History**")
                show_table(
                    pd.DataFrame(st.session_state.intervention_log),
                    width="stretch",
                )
