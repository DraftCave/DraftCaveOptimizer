from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "apply_live_build_ui_v6.py"

text = SCRIPT.read_text(encoding="utf-8")

old = '''css_start = \'\'\'    .st-key-generate_action {\\n        position: fixed; bottom: 0.5rem; right: 1rem; z-index: 100;\\n        width: min(340px, calc(100vw - 2rem)); padding: 0.6rem;\\n        background: var(--dc-panel); border: 1px solid var(--dc-border);\\n        border-radius: 10px; box-shadow: 0 4px 24px #0008;\\n    }\\n\'\'\'\ntheme = replace_once(\n    theme,\n    css_start,\n    \'\'\'    .st-key-generate_action {\\n        margin-top: 0.35rem;\\n        margin-bottom: 0.6rem;\\n    }\\n\'\'\','''

new = '''css_start = \'\'\'    .st-key-generate_action {{\\n        position: fixed; bottom: 0.5rem; right: 1rem; z-index: 100;\\n        width: min(340px, calc(100vw - 2rem)); padding: 0.6rem;\\n        background: var(--dc-panel); border: 1px solid var(--dc-border);\\n        border-radius: 10px; box-shadow: 0 4px 24px #0008;\\n    }}\\n\'\'\'\ntheme = replace_once(\n    theme,\n    css_start,\n    \'\'\'    .st-key-generate_action {{\\n        margin-top: 0.35rem;\\n        margin-bottom: 0.6rem;\\n    }}\\n\'\'\','''

if old not in text:
    raise RuntimeError("Expected V6 CSS matcher block was not found; no changes made.")

text = text.replace(old, new, 1)
compile(text, str(SCRIPT), "exec")
SCRIPT.write_text(text, encoding="utf-8")

print("Fixed apply_live_build_ui_v6.py CSS matcher")
print("Now rerun: py -3.14 tools\\apply_live_build_ui_v6.py")
