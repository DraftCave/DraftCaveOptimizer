# Production UI V1 validation — 2026-10-29

- Full pytest: **101 passed** (11.51 seconds), Python 3.12 / Streamlit 1.66.1.
- Local browser inspection: main screen and compact 15-row Player Pool at 1280 × 720. Fixed header overlap. Screenshots use synthetic AAA–FFF players, not a current NFL slate.
- Existing integration checks cover pool exclusions, locks, position bulk edits, generation, result persistence/restoration, and API serialization. Added seven-button sentiment/projection invariance and corrupt-image fallback checks.
- Optimizer, configuration defaults, data loader, portfolio algorithms, exporter, API implementation, and last-run cache functions unchanged.
- CI dependencies: retain `httpx2` and add `httpx` for the older TestClient versions permitted by the existing FastAPI range. Integration tests now create temporary synthetic slate files instead of requiring untracked private data.
- Sentiment interaction: choose an explicit DK-ID player, then click a face; grid displays the stored semantic state. BAN excludes; changing away from BAN does not silently re-add a player. Locks remain independent.
- Local assets only: exact DK-ID headshot → exact team logo → placeholder. No bundled real player images or external identity lookup. File update timestamps are labeled as file metadata, not verified projection freshness.
- Final selection and contest allocation remain available under Portfolio Risk. Export remains a dedicated tab. No merge to main.

![Main screen](screenshots/ui-main.jpg)
![Player Pool](screenshots/ui-pool.jpg)
