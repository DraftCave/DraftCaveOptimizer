from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"

text = APP.read_text(encoding="utf-8")
lines = text.splitlines()

TARGETS = [
    "Show research columns",
    "DVP · green",
    'key="active_position"',
    'key="pool_sort"',
    "header_controls = st.columns",
    '"Min %"',
    '"Max %"',
    "Compact vertical lineup cards",
    "&nbsp;",
    "reservoir_metrics[4].metric",
    "Data Status · details",
]

print("READ-ONLY LOCAL UI INSPECTION")
print(f"File: {APP}")
print(f"Lines: {len(lines)}")
print("No files will be modified.\n")

seen_ranges: set[tuple[int, int]] = set()
for target in TARGETS:
    matches = [i for i, line in enumerate(lines) if target in line]
    print("=" * 88)
    print(f"TARGET: {target!r} | matches={len(matches)}")
    if not matches:
        continue
    for idx in matches[:4]:
        start = max(0, idx - 12)
        end = min(len(lines), idx + 18)
        key = (start, end)
        if key in seen_ranges:
            continue
        seen_ranges.add(key)
        print(f"--- lines {start + 1}-{end} ---")
        for n in range(start, end):
            print(f"{n + 1:04d}: {lines[n]}")

print("=" * 88)
print("COUNTS")
for target in TARGETS:
    print(f"{target!r}: {text.count(target)}")
