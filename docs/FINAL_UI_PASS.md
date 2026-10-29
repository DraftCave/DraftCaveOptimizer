# Draft Cave Optimizer — Final UI Pass

Purpose: make the next Work session short and deterministic. Do not re-audit the product or redesign the optimizer.

Branch: `production-ui-v1`
Base: `main` known-good baseline at `2c6d985`
PR: #1

## Non-negotiable guardrails

- Do not change optimizer math, lineup-generation semantics, projections, ownership values, exposure rules, roster identity, exporter behavior, or last-run persistence.
- DraftKings ID remains canonical player identity.
- No fuzzy player identity matching.
- No external player-image lookup.
- Missing ownership and ceiling remain `—`, never 0.
- `main` stays untouched until final review.
- Do not merge during this pass.

## Already implemented and must be preserved

- black / midnight navy / cool-blue Draft Cave theme
- restrained gold Generate action
- compact data/status strip
- Build / Correlation / Portfolio / Advanced settings
- Player Pool position tabs and filters
- Player name protected near the far left
- default compact identity order: `In Pool | Player | Pos | Team | Opp | ...`
- standalone image column suppressed when it would crowd Player
- local visual resolver: exact DK-ID headshot -> exact team logo -> placeholder
- lock / pool / BAN remain separate concepts
- position-only bulk Min/Max exposure controls
- active RB bulk exposure must not affect QB/WR/TE/DST, and same rule for every other position
- exact sentiment semantics:
  - ADORE +10%
  - LOVE +7.5%
  - LIKE +5%
  - NEUTRAL 0%
  - DISLIKE -5%
  - HATE -10%
  - BAN exclude
- sentiment never mutates stored/displayed projection
- Results tabs exactly:
  - Lineups
  - Exposure
  - Stacks & Games
  - Portfolio Risk
  - Repetition
  - Export
- no fake `Low Dup`, lineup grade, subjective matchup grade, or generic quality score

## Task 1 — Final DS-style sentiment interaction

Replace the temporary explicit-player + permanently visible seven-button surface.

Target interaction:

1. Each player row shows only the player's current sentiment face/state by default.
2. Neutral starts as a single neutral face.
3. Clicking the face opens a compact popover/menu.
4. The popover shows all seven choices with labels and exact existing semantics.
5. Selecting a state closes/updates the control and the row shows the newly selected face.
6. BAN excludes the player.
7. Moving away from BAN must not silently re-add the player to the pool; manual exclusion state remains explicit.
8. Lock state remains independent.

Preferred visual order near the left side:

`In Pool | Lock | Sentiment | Player | Pos | Team | Opp | ...`

If Streamlit's standard `st.data_editor` cannot support a true row-level popover reliably, use the smallest maintainable Streamlit-native alternative. Do not build a custom frontend framework for V1. The UX goal matters more than literal implementation parity.

## Task 2 — Player visual reintegration only if safe

Try to show the existing local headshot/team-logo fallback immediately adjacent to the Player name without reducing name readability or materially increasing row height.

Acceptance:
- Player name remains clearly visible at 1280px width.
- image failure never breaks the row.
- no separate wide image column.

If this cannot be done cleanly in Streamlit V1, leave visuals suppressed in the table. Player-name readability wins.

## Task 3 — Results/header polish

Inspect the six Results tabs and top status strip.

Only make obvious presentation fixes:
- compact spacing
- readable labels
- no duplicate headings
- no fake metrics
- no source/provider branding in the top status strip
- warnings remain prominent when they invalidate a build

Do not invent new analytical features.

## Task 4 — Browser validation

Launch Streamlit locally and inspect at least:
- 1280x720
- a wider desktop viewport if available

Verify:
- Player names visible on every row
- no horizontal layout makes identity unreadable
- position bulk exposure controls are understandable
- sentiment interaction is compact
- Generate action remains easy to find
- all six Results tabs are readable
- no header overlap
- no broken images
- no fake values

Use synthetic/private-safe data only for screenshots committed to the public repository.

## Task 5 — Tests

Run full pytest.

Must preserve/regressions already covered:
- locks
- exclusions
- BAN
- sentiment projection invariance
- bulk Min/Max position isolation
- missing ownership/ceiling
- generation
- result persistence/restoration
- API serialization
- player visual fallback
- player-name identity guard

Add only the smallest tests required for the new sentiment interaction.

## Completion output

Before stopping:
- commit validated changes to `production-ui-v1`
- push branch
- refresh screenshots if the UI materially changed
- update `docs/UI_VALIDATION_V1.md`
- update PR #1 with final validation summary
- report exact pytest count/result
- report any remaining visual limitation honestly
- do not merge to `main`
