from __future__ import annotations


DRAFT_CAVE_GOLD = "#F4BE45"
DRAFT_CAVE_GOLD_HOVER = "#FFD56B"
DRAFT_CAVE_BG = "#071018"
DRAFT_CAVE_PANEL = "#0C1721"
DRAFT_CAVE_PANEL_ALT = "#101D28"
DRAFT_CAVE_BORDER = "#24323E"
DRAFT_CAVE_TEXT = "#EEF3F7"
DRAFT_CAVE_MUTED = "#8A99A7"
DRAFT_CAVE_GREEN = "#36C98F"
DRAFT_CAVE_RED = "#F16464"
DRAFT_CAVE_AMBER = "#E6A93E"


def app_css() -> str:
    """Return presentation-only CSS for the Streamlit application.

    Gold is reserved for selected/action states. Green/red/amber are reserved
    for status and movement signals, not decorative styling.
    """

    return f"""
    <style>
    :root {{
        --dc-gold: {DRAFT_CAVE_GOLD};
        --dc-gold-hover: {DRAFT_CAVE_GOLD_HOVER};
        --dc-bg: {DRAFT_CAVE_BG};
        --dc-panel: {DRAFT_CAVE_PANEL};
        --dc-panel-alt: {DRAFT_CAVE_PANEL_ALT};
        --dc-border: {DRAFT_CAVE_BORDER};
        --dc-text: {DRAFT_CAVE_TEXT};
        --dc-muted: {DRAFT_CAVE_MUTED};
        --dc-green: {DRAFT_CAVE_GREEN};
        --dc-red: {DRAFT_CAVE_RED};
        --dc-amber: {DRAFT_CAVE_AMBER};
    }}

    .stApp {{
        background: linear-gradient(180deg, #071018 0%, #08121B 48%, #060D13 100%);
        color: var(--dc-text);
    }}

    [data-testid="stHeader"] {{
        background: rgba(7, 16, 24, 0.88);
    }}

    [data-testid="stMainBlockContainer"] {{
        max-width: 1840px;
        padding-top: 0.7rem;
        padding-left: 1rem;
        padding-right: 1rem;
        padding-bottom: 2.25rem;
    }}

    [data-testid="stVerticalBlockBorderWrapper"] {{
        border-color: var(--dc-border) !important;
        background: rgba(12, 23, 33, 0.94);
        border-radius: 12px;
    }}

    .dc-panel-title {{
        color: var(--dc-text);
        font-size: 1.03rem;
        font-weight: 750;
        letter-spacing: -0.01em;
    }}

    .dc-section-label,
    .dc-gold {{
        color: var(--dc-gold);
    }}

    .dc-muted {{
        color: var(--dc-muted);
    }}

    .stButton > button {{
        border-radius: 8px;
        border: 1px solid var(--dc-border);
        background: #0C1923;
        color: #DDE6EC;
        min-height: 2.25rem;
        font-weight: 650;
    }}

    .stButton > button:hover {{
        border-color: var(--dc-gold);
        color: #FFFFFF;
        background: #15212A;
        box-shadow: 0 0 0 1px rgba(244, 190, 69, 0.14);
    }}

    .stButton > button[kind="primary"] {{
        background: linear-gradient(180deg, var(--dc-gold-hover), var(--dc-gold));
        border-color: var(--dc-gold);
        color: #111820;
        font-weight: 800;
        box-shadow: 0 6px 20px rgba(244, 190, 69, 0.18);
    }}

    .stButton > button[kind="primary"]:hover {{
        background: var(--dc-gold-hover);
        box-shadow: 0 8px 24px rgba(244, 190, 69, 0.25);
    }}

    div[role="radiogroup"] label {{
        border: 1px solid var(--dc-border);
        border-radius: 8px;
        background: #0D1821;
        padding: 0.3rem 0.7rem;
    }}

    div[role="radiogroup"] label:has(input:checked) {{
        background: linear-gradient(180deg, var(--dc-gold-hover), var(--dc-gold));
        border-color: var(--dc-gold);
        color: #111820 !important;
        box-shadow: 0 3px 12px rgba(244, 190, 69, 0.2);
    }}

    div[role="radiogroup"] label:has(input:checked) p {{
        color: #111820 !important;
        font-weight: 800;
    }}

    button[data-baseweb="tab"][aria-selected="true"] {{
        color: var(--dc-gold) !important;
    }}

    [data-testid="stDataFrame"] {{
        border: 1px solid var(--dc-border);
        border-radius: 9px;
        overflow: hidden;
    }}

    #MainMenu, footer {{
        visibility: hidden;
    }}
    </style>
    """
