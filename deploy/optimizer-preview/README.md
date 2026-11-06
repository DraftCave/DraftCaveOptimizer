# Isolated optimizer preview package

Use this directory as the Vercel **Root Directory**: `deploy/optimizer-preview`.
Do not use the repository root, whose app.py is the existing Streamlit application.

The package copies the locally accepted Sprint 1 backend without changing its behavior.
`app.py` exports `backend.website:app`, not the unauthenticated legacy `backend.api:app`.
Python is pinned to 3.12; requirements.txt pins all 23 runtime dependencies.
The original application and root requirements remain unchanged.

## Before any future deployment

- Use only a separate protected preview project on Hobby, with Fluid Compute and standard 2 GB memory. Do not change production aliases or attach custom domains.
- Verify Vercel Authentication preview protection before deploying. vercel.json does not configure account-level protection or force preview targeting.
- Configure a new server-only sensitive `DRAFT_CAVE_OPTIMIZER_KEY` for Preview only; no value is provided or configured here.
- Configure Preview `DRAFT_CAVE_OPTIMIZER_MANIFEST=snapshot/manifest.json`.
- Confirm the deployment target is Preview. Do not promote it to production.
- Stop if permissions, protection, or required configuration cannot be established.

The bundled 36-player snapshot is synthetic, labeled TECHNICAL_REPLAY, and verified by SHA256. Missing configuration fails closed. No Warehouse files, submitted portfolios, or live-slate inputs are included.

For a future startup check, GET /snapshot with the service Bearer key after passing Vercel protection. Without the application key, expect 401; with missing service configuration, expect 503. There is no separate public health endpoint. No lineup generation is needed for a startup check.

The packaging checkpoint measured 195,373,637 bytes including installed Linux wheels and the synthetic snapshot, before these small deployment metadata files. Linux imports and Vercel's final artifact size have not been verified. The runtime, memory, and determinism acceptance checks remain separate future work.

Prior project creation failed with Vercel 403 Forbidden. This package does not resolve that account permission blocker. This branch was prepared locally without pushing, to avoid triggering a Git-connected deployment.
