# Draft Cave Optimizer — UI Contract V1

Status: LOCKED FOR IMPLEMENTATION on `production-ui-v1`

This document defines the visual and interaction target for the first production UI pass. It is intentionally UI-only. It must not change optimizer math, lineup-generation semantics, projections, ownership values, exposure rules, or export behavior.

## 1. Overall direction

Use the approved dark Draft Cave command-center mockup as the visual reference.

- Dark charcoal / near-black primary canvas.
- Draft Cave gold is the primary action / selected-state accent.
- Green/red are reserved for actual positive/negative status or movement.
- Gray is neutral.
- Reduce blue-heavy styling from the current Streamlit implementation.
- Dense professional DFS-tool feel; avoid oversized cards or mobile-game styling.
- Prefer spacing and subtle panel contrast over excessive nested borders.
- Optimize for desktop use and fast Sunday scanning.

## 2. Top status strip

The top strip must be compact and source-agnostic.

Show:
- slate identifier / date when available,
- data freshness / last update,
- matched players,
- unresolved identities,
- last optimizer run status / time when available.

Do NOT show provider/source branding in the top status strip.

Use small green / amber / red health indicators where appropriate.

Ownership or projection staleness must be visible. Missing values must display as `—`, never silently as zero.

## 3. Main page hierarchy

Primary hierarchy:

1. Status strip
2. Settings + Player Pool
3. Generate action
4. Results

Avoid the current long-form sequence of upload boxes -> settings -> more settings -> diagnostics -> player pool -> output.

Player Pool should be the visual center of the product and receive the majority of horizontal space.

## 4. Settings organization

Use four logical groups:

### Build
High-frequency controls such as:
- candidate lineups,
- minimum uniques,
- salary floor,
- randomization,
- preset where still useful.

### Correlation
- QB stack min/max,
- bring-back,
- secondary stack,
- same-team SIM,
- opponent SIM.

### Portfolio
- total lineup projected ownership band when available,
- RB FLEX max,
- WR FLEX max,
- TE FLEX max,
- other validated portfolio constraints that already exist.

### Advanced
Default collapsed.

May include:
- random seed,
- StatRankings influence,
- opposing DST rule,
- QB/RB rule,
- QB/DST rule,
- diagnostics / intervention log.

No fake quality controls or arbitrary ratings.

## 5. Generate action

The Generate button must be visually prominent and Draft Cave gold.

Preferred label includes the active requested count, e.g.:

`GENERATE 60 LINEUPS`

It should remain easy to locate even when settings are collapsed.

## 6. Player Pool

Position tabs remain:

`ALL | QB | RB | WR | TE | DST`

The table should be compact enough to show roughly 12–15 rows on a standard desktop viewport where practical.

### Default visible columns

Target default scan order:

- In Pool
- Player identity
- Team
- Opp
- Pos
- Salary
- Proj
- Own%
- Ceiling
- Value
- Sentiment
- Min%
- Max%

Research-only fields such as Role / Form / Environment / Edge / injury details should be hidden behind an optional research/details view rather than occupying the default table.

Do NOT show a subjective `Good / Neutral / Bad` matchup label.

Do NOT show an unvalidated `Low Dup` or similar duplication badge.

## 7. Player identity visuals

Preferred hierarchy:

1. small player headshot when a reliable image exists,
2. team logo as persistent supporting identity and as fallback,
3. compact placeholder only if neither is available.

Implementation requirements:
- headshot target size about 24–28 px,
- team logo target size about 18–24 px,
- visuals live inside or immediately adjacent to the Player name cell,
- do not materially increase row height,
- do not block table rendering if images fail,
- image availability must never affect optimizer identity resolution.

Preferred player-name cell visual:

`[headshot] Player Name`
`[team logo] POS • TEAM`

If headshot support proves too fragile for V1, ship team logos first and add headshots as progressive enhancement.

## 8. In Pool / Lock behavior

`In Pool` remains a simple checkbox.

Lock remains visually distinct from exclusion. A lock icon / compact lock control is preferred over an additional bulky checkbox column.

BAN sentiment may exclude a player, but manual pool exclusion and lock state remain separate concepts internally and visually.

## 9. Sentiment control

Do NOT use a dropdown in the production UI.

Use a DS-style one-click icon / face control.

Approved sentiment states and optimizer semantics remain:

- ADORE: +10%
- LOVE: +7.5%
- LIKE: +5%
- NEUTRAL: 0%
- DISLIKE: -5%
- HATE: -10%
- BAN: exclude

The UI may compress these into recognizable one-click icons/faces, but the stored semantic state must remain explicit and unchanged.

Suggested visual scale:

- 😍 Adore
- ❤️ / 🙂 Love
- 👍 Like
- 😐 Neutral
- 👎 Dislike
- 😡 Hate
- ⛔ Ban

The selected state should use a subtle ring/background rather than a large dropdown.

Sentiment remains objective-only and must never mutate displayed/stored projections.

## 10. Metric emphasis

Visually prioritize:

- Projection
- Ceiling
- Own%
- Value

Salary / Team / Opp remain readable but secondary.

Future snapshot movement may be shown compactly beside a metric, for example:

- `17.8% ▲ 2.4`
- `18.6 ▼ 0.8`

Movement is only shown when backed by actual prior snapshots.

## 11. Exposure controls

Player Min% / Max% fields remain compact.

Position-wide bulk Min/Max controls may remain but must not dominate the page.

Do not add a redundant second position selector when the active position tab already defines the bulk-edit target.

## 12. Results navigation

Use these result tabs:

`Lineups | Exposure | Stacks & Games | Portfolio Risk | Repetition | Export`

### Lineups
Show lineup construction clearly. QB should be visually distinct. Correlated teammates and bring-backs may receive subtle markers so the scoring story can be understood at a glance.

### Exposure
Player and QB exposure. Keep projected ownership distinct from optimizer exposure.

### Stacks & Games
QB/game/story-family representation and stack structure.

### Portfolio Risk
Concentration, effective player count, effective QB count, joint risk-factor overlap when available.

### Repetition
Repeated pairs, repeated cores, overlap/search-density diagnostics.

### Export
Dedicated DraftKings export validation and download surface.

## 13. Results header metrics

Only show real, inspectable metrics such as:

- lineups generated,
- average / median projection,
- average / median salary,
- average cumulative projected ownership when available,
- effective player count,
- effective QB count.

Remove / never add fake metrics such as:

- arbitrary lineup grade,
- generic quality score,
- unvalidated duplication score,
- `good/neutral` matchup score presented as truth.

## 14. Diagnostics

Diagnostics must stay available but out of the primary workflow unless something is wrong.

Examples:
- unresolved identities,
- stale source data,
- missing ownership,
- infeasible constraints,
- seed,
- StatRankings status,
- source fingerprint / run provenance.

Warnings that can invalidate a build should become visually prominent automatically.

## 15. Data integrity rules for UI

The UI must not manufacture certainty.

- Missing ownership = `—`, not 0%.
- Missing ceiling = `—`.
- Missing image = fallback, not a broken row.
- Unresolved player identity must remain visible and block dependent logic where required.
- Projected ownership and generated exposure must never be labeled interchangeably.
- Source/provider names are allowed in diagnostics/details but not required in the top status strip.

## 16. Implementation order

1. Restructure visual hierarchy without changing optimizer semantics.
2. Replace sentiment dropdown with one-click icon control.
3. Tighten default player columns and row density.
4. Add team-logo identity support with safe fallback.
5. Add player headshots where reliable, with team-logo fallback.
6. Reorganize Results into locked tab structure.
7. Add compact status/freshness strip.
8. Add snapshot delta presentation when snapshot history exists.
9. Run full existing test suite after every behavior-adjacent change.
10. Do not merge to `main` until parity and manual UI review are complete.
