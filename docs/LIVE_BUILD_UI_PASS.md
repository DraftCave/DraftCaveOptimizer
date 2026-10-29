# Live build UI pass — 2026-10-29

Branch: `production-ui-v1`. No merge to main.

The previously committed target/V2/V3/V4/V5 patch scripts were incorporated into
the app so the checkout retains row sentiment editing, sentiment-adjusted display
projection, compact position exposure controls, and Portfolio Review. Explicit
locks remain available under collapsed Advanced player controls; they are not
silently cleared. Do not rerun those historical patch scripts on this version.

## Behavior

- Team and Opp cells contain a 24px logo plus the slate's abbreviation, rendered
  together in a single local image. Unknown/corrupt assets fall back to the
  abbreviation. Plain text is also available as Team Abbr / Opp Abbr in research
  columns. Images never resolve player identities.
- Sort and Order are session-state controls. Numeric ownership/ceiling values,
  missing values last, and deterministic DK-ID ties avoid string-sort errors.
  Header sorting remains temporary; use Sort for persistence.
- Editor callbacks receive the exact displayed ID order. Changing sort/filter
  order changes the editor key, discarding stale row-index deltas.
- Player Pool position survives edits and generation. Successful generation
  opens Portfolio Review on that position; users may independently change the
  review position afterward. Reset Filters intentionally selects ALL.
- Generate/Regenerate and Clear Results remain fixed at the lower right. Bottom
  padding keeps the final content reachable. This uses the existing generation
  path and last-run persistence.
- Noncritical unresolved-row details are inside Data Status. Counts remain in
  the compact status line; input failures and zero projection coverage remain
  prominent. The control summary is one line.

## DVP source gap and ingestion contract

No verified current DVP source was found in the app's supplied data or loader.
StatRankings `Matchup_Score` is not DVP and is never relabeled as DVP. Current
values remain missing, with an explicit unavailable message. No matchup model,
projection multiplier, ownership change, or optimizer weight was introduced.

Supply `data/dvp.json` after independently verifying the provider's slate/date,
position semantics, and rank direction. Metadata records that human verification;
the loader cannot independently certify a provider's claim. The salary SHA-256
shown in Data Status binds the snapshot to the exact uploaded/local salary file.
Use this schema (placeholders below are documentation, not usable matchup data):

```json
{
  "salary_sha256": "<SHA-256 shown in Data Status>",
  "rank_direction": "1_easiest_32_hardest",
  "source": "<verified provider and metric>",
  "source_url": "<original evidence URL>",
  "as_of": "<ISO-8601 source timestamp>",
  "verified_by": "<reviewer or verified ingestion job>",
  "rows": [
    {"opponent": "<exact slate opponent>", "position": "<exact slate position>", "rank": null}
  ]
}
```

`rank` is an integer 1–32 or null. Direction is **1 easiest, 32 hardest**;
normalize a provider's inverse convention explicitly before supplying data.
Colors are display bins: green 1–8, yellow 9–16, orange 17–24, red 25–32.
These bins are not validated predictive thresholds. Missing combinations and
null ranks remain missing. Wrong slate fingerprints, duplicate/unresolved
opponent-position keys, invalid ranks, malformed JSON, or missing provenance
reject the snapshot and show a diagnostic. Partial coverage is allowed. DST
must have separately verified semantics; never infer it from offensive DVP.

DVP lives only in `ui_matchups.py` and the presentation dataframe. It is not
added to Player, OptimizerSettings, the objective, candidate generation,
selection, source projections, or DraftKings export. Current-slate research
and continuity reference files were not modified by this UI-only pass.

## Validation

- Full regression suite: 118 tests passed, including real Streamlit AppTest
  edits and generation, optimizer, API, export, and persistence checks.
- Numeric sort, missing-last ordering, deterministic ties, sorted row exclusion,
  sentiment/Min/Max updates, re-sorting without identity drift, position
  retention, and generated review position tested.
- Adding valid synthetic DVP leaves solver inputs and generated lineup ID sets
  identical; source projections remain unchanged.
- All 34 team/alias PNG files decoded successfully. Browser preview verified
  collapsed diagnostics, abbreviation fallbacks, and fixed Generate access.
- `optimizer.py`, `config.py`, `models.py`, `data_loader.py`, `portfolio.py`,
  `exporter.py`, `backend/api.py`, and `statrankings.py` are byte-identical to
  branch checkpoint `9a169cf`.
- Tests use isolated synthetic slates, not live lineup recommendations. The
  restricted runner had temporary-directory access problems; the successful
  full suite ran with normal local permissions.
