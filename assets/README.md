# Draft Cave Optimizer visual assets

These files are presentation-only. They must never be used to resolve player identity for optimizer logic.

## Player headshots

Store optional player images under:

`assets/players/<DK_ID>.<ext>`

Supported extensions: `.png`, `.webp`, `.jpg`, `.jpeg`.

The DraftKings player ID is the only supported filename key. Do not use fuzzy name matching.

## Team logos

Store optional team logos under:

`assets/teams/<TEAM>.<ext>`

Use the canonical team abbreviation already present on the current DraftKings slate, uppercased.

## Fallback order

1. Player headshot by DraftKings ID
2. Team logo by exact team abbreviation
3. Text placeholder

No network lookup is performed by the resolver. This prevents stale image sources, broken external URLs, and visual identity from contaminating roster identity.

## Bundled team assets (2026-10-29)

32 NFL team PNGs were downloaded from ESPN's team-logo CDN:
`https://a.espncdn.com/i/teamlogos/nfl/500/<provider-code>.png`.
Provider codes are lowercase filenames, except WAS uses `wsh`.
LA is a copy of LAR, and WSH is a copy of WAS (34 files total).
These are team artwork assets, not player/team assignment evidence.
Team marks belong to their respective owners; no ownership of the artwork is claimed.
The app performs no image network requests at runtime.
