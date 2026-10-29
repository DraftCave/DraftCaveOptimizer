from __future__ import annotations

from functools import wraps

import streamlit as st


# Draft Cave visual system: black / midnight navy / cool blue first.
# Gold is intentionally reserved for premium emphasis, never the core interaction color.
DRAFT_CAVE_BG = "#050A0F"
DRAFT_CAVE_BG_ALT = "#07111F"
DRAFT_CAVE_PANEL = "#0D1B2A"
DRAFT_CAVE_PANEL_ALT = "#13283D"
DRAFT_CAVE_BORDER = "#1D3550"
DRAFT_CAVE_BLUE = "#1EA7FF"
DRAFT_CAVE_BLUE_HOVER = "#4DB9FF"
DRAFT_CAVE_BLUE_MUTED = "#6CBDF2"
DRAFT_CAVE_GOLD = "#D8A84E"
DRAFT_CAVE_TEXT = "#EAF2FA"
DRAFT_CAVE_MUTED = "#8296AD"
DRAFT_CAVE_GREEN = "#36C98F"
DRAFT_CAVE_RED = "#F16464"
DRAFT_CAVE_AMBER = "#E6A93E"


def _install_player_pool_identity_guard() -> None:
    """Keep player names visible in the compact Player Pool.

    Streamlit's data editor can squeeze the Player column when a standalone
    ImageColumn sits immediately before it at common laptop/browser widths.
    The optimizer already keeps the visual asset data, so the safest interim
    presentation fix is to hide only that standalone image column in the
    default Player Pool view and force Player to a large, left-anchored column.

    This wrapper is scoped only to the Player Pool editor key and never changes
    optimizer data, controls, projections, exposures, or export behavior.
    """

    current = st.data_editor
    if getattr(current, "_draft_cave_identity_guard", False):
        return

    @wraps(current)
    def guarded_data_editor(data, *args, **kwargs):
        key = str(kwargs.get("key", ""))
        if key.startswith("player_pool_editor_v5_"):
            column_order = list(kwargs.get("column_order") or [])
            if "Player" in column_order:
                # The visual asset remains in the backing dataframe for future
                # headshot/logo identity-cell polish, but does not consume a
                # separate default column while names are the priority.
                column_order = [column for column in column_order if column != "Visual"]
                column_order = [column for column in column_order if column != "Player"]
                insert_at = 1 if "In Pool" in column_order else 0
                column_order.insert(insert_at, "Player")

                # Keep the compact DS-style identity sequence near the left.
                preferred = ["In Pool", "Player", "Pos", "Team", "Opp"]
                ordered = [column for column in preferred if column in column_order]
                ordered += [column for column in column_order if column not in ordered]
                kwargs["column_order"] = ordered

            column_config = dict(kwargs.get("column_config") or {})
            column_config["Player"] = st.column_config.TextColumn(
                "Player",
                width="large",
                help="Player name — always visible in the default pool view.",
            )
            kwargs["column_config"] = column_config

        return current(data, *args, **kwargs)

    guarded_data_editor._draft_cave_identity_guard = True
    st.data_editor = guarded_data_editor


def app_css() -> str:
    """Return presentation-only CSS for the Streamlit application.

    Blue is the primary interaction accent. Gold is reserved for premium or
    special emphasis only. Green/red/amber remain semantic status colors.
    """

    _install_player_pool_identity_guard()

    return f"""
    <style>
    :root {{
        --dc-bg: {DRAFT_CAVE_BG};
        --dc-bg-alt: {DRAFT_CAVE_BG_ALT};
        --dc-panel: {DRAFT_CAVE_PANEL};
        --dc-panel-alt: {DRAFT_CAVE_PANEL_ALT};
        --dc-border: {DRAFT_CAVE_BORDER};
        --dc-blue: {DRAFT_CAVE_BLUE};
        --dc-blue-hover: {DRAFT_CAVE_BLUE_HOVER};
        --dc-blue-muted: {DRAFT_CAVE_BLUE_MUTED};
        --dc-gold: {DRAFT_CAVE_GOLD};
        --dc-text: {DRAFT_CAVE_TEXT};
        --dc-muted: {DRAFT_CAVE_MUTED};
        --dc-green: {DRAFT_CAVE_GREEN};
        --dc-red: {DRAFT_CAVE_RED};
        --dc-amber: {DRAFT_CAVE_AMBER};
    }}

    .stApp {{
        background:
            radial-gradient(circle at top left, rgba(30, 167, 255, 0.10), transparent 28%),
            linear-gradient(180deg, var(--dc-bg-alt) 0%, #07101A 48%, var(--dc-bg) 100%);
        color: var(--dc-text);
    }}

    [data-testid="stHeader"] {{
        background: rgba(5, 10, 15, 0.88);
    }}

    [data-testid="stMainBlockContainer"] {{
        max-width: 1840px;
        padding-top: 4rem;
        padding-left: 1rem;
        padding-right: 1rem;
        padding-bottom: 2.25rem;
    }}

    [data-testid="stVerticalBlockBorderWrapper"] {{
        border-color: var(--dc-border) !important;
        background: rgba(13, 27, 42, 0.94);
        border-radius: 12px;
    }}

    .dc-panel-title {{
        color: var(--dc-text);
        font-size: 1.03rem;
        font-weight: 750;
        letter-spacing: -0.01em;
    }}

    .dc-section-label,
    .dc-blue {{
        color: var(--dc-blue);
    }}

    .dc-gold {{
        color: var(--dc-gold);
    }}

    .dc-muted {{
        color: var(--dc-muted);
    }}

    .stButton > button {{
        border-radius: 8px;
        border: 1px solid var(--dc-border);
        background: #0B1724;
        color: #DDE8F2;
        min-height: 2.25rem;
        font-weight: 650;
    }}

    .stButton > button:hover {{
        border-color: var(--dc-blue);
        color: #FFFFFF;
        background: #10263A;
        box-shadow: 0 0 0 1px rgba(30, 167, 255, 0.14);
    }}

    .stButton > button[kind="primary"] {{
        background: linear-gradient(180deg, var(--dc-blue-hover), var(--dc-blue));
        border-color: var(--dc-blue);
        color: #FFFFFF;
        font-weight: 800;
        box-shadow: 0 6px 20px rgba(30, 167, 255, 0.20);
    }}

    .stButton > button[kind="primary"]:hover {{
        background: var(--dc-blue-hover);
        box-shadow: 0 8px 24px rgba(30, 167, 255, 0.27);
    }}

    div[role="radiogroup"] label {{
        border: 1px solid var(--dc-border);
        border-radius: 8px;
        background: #0C1826;
        padding: 0.3rem 0.7rem;
    }}

    div[role="radiogroup"] label:has(input:checked) {{
        background: linear-gradient(180deg, var(--dc-blue-hover), var(--dc-blue));
        border-color: var(--dc-blue);
        color: #FFFFFF !important;
        box-shadow: 0 3px 12px rgba(30, 167, 255, 0.22);
    }}

    div[role="radiogroup"] label:has(input:checked) p {{
        color: #FFFFFF !important;
        font-weight: 800;
    }}

    button[data-baseweb="tab"][aria-selected="true"] {{
        color: var(--dc-blue) !important;
    }}

    [data-testid="stDataFrame"] {{
        border: 1px solid var(--dc-border);
        border-radius: 9px;
        overflow: hidden;
    }}

    .dc-header {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:0.5rem; }}
    .dc-brand {{ display:flex; align-items:center; gap:0.7rem; }}
    .dc-logo {{ font-size:1.7rem; }}
    .dc-brand-title {{ font-size:1.2rem; font-weight:800; letter-spacing:0.12em; }}
    .dc-brand-sub, .dc-header-badge {{ font-size:0.65rem; color:var(--dc-muted); letter-spacing:0.1em; }}
    [data-testid="stVerticalBlock"] {{ gap:0.65rem; }}
    [data-testid="stMetricValue"] {{ font-size:1.35rem; }}
    .st-key-generate_action button[kind="primary"],
    .st-key-generate_action button[kind="primary"]:hover {{
        background:var(--dc-gold); border-color:var(--dc-gold); color:var(--dc-bg); box-shadow:none;
    }}
    #MainMenu, footer {{
        visibility: hidden;
    }}
    </style>
    """
