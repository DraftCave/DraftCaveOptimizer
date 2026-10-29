from __future__ import annotations


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


def app_css() -> str:
    """Return presentation-only CSS for the Streamlit application.

    Blue is the primary interaction accent. Gold is reserved for premium or
    special emphasis only. Green/red/amber remain semantic status colors.
    """

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
        padding-top: 0.7rem;
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

    #MainMenu, footer {{
        visibility: hidden;
    }}
    </style>
    """
