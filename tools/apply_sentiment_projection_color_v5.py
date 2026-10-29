from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(
            f"Could not find {label}; local app.py may differ from the expected V4 checkpoint."
        )
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8")

# Require the sentiment-adjusted projection checkpoint first.
for marker in (
    '"Base Proj": base_projection',
    '"Proj": display_projection',
    'show_research_columns_v5',
):
    if marker not in app:
        raise RuntimeError(
            "This patch expects sentiment projection V4 to already be applied. "
            f"Missing marker: {marker}"
        )

# Style only the read-only Proj cell. Green = above source projection,
# red = below source projection, neutral = unchanged. Base Proj remains canonical.
anchor = '''    editor_key = f"player_pool_editor_v5_{st.session_state.get('pool_editor_revision', 0)}"\n    edited_pool_df = st.data_editor(\n        pool_df,\n'''
replacement = '''    def _projection_sentiment_style(row):\n        styles = ["" for _ in row.index]\n        if "Proj" not in row.index or "Base Proj" not in row.index:\n            return styles\n\n        proj = row.get("Proj")\n        base = row.get("Base Proj")\n        if pd.isna(proj) or pd.isna(base):\n            return styles\n\n        proj_idx = row.index.get_loc("Proj")\n        if float(proj) > float(base) + 1e-9:\n            styles[proj_idx] = (\n                "background-color: rgba(54, 201, 143, 0.22); "\n                "color: #7BE0B7; font-weight: 800;"\n            )\n        elif float(proj) < float(base) - 1e-9:\n            styles[proj_idx] = (\n                "background-color: rgba(241, 100, 100, 0.22); "\n                "color: #FF9B9B; font-weight: 800;"\n            )\n        return styles\n\n    styled_pool_df = pool_df.style.apply(_projection_sentiment_style, axis=1)\n\n    editor_key = f"player_pool_editor_v5_{st.session_state.get('pool_editor_revision', 0)}"\n    edited_pool_df = st.data_editor(\n        styled_pool_df,\n'''
app = replace_once(app, anchor, replacement, "Player Pool data editor input")

compile(app, str(APP), "exec")

backup_dir = ROOT / "repair_backup_20261029"
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "app_before_sentiment_projection_color_v5.py"
if not backup.exists():
    backup.write_text(APP.read_text(encoding="utf-8"), encoding="utf-8")

APP.write_text(app, encoding="utf-8")
print("Applied sentiment projection color V5")
print("- positive sentiment-adjusted Proj cells highlight green")
print("- negative sentiment-adjusted Proj cells highlight red")
print("- neutral Proj cells remain unchanged")
print("- optimizer math and Base Proj remain unchanged")
