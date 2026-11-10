# Draft Cave Week 10 Python engine engineering preview

Test-only backend copied from DraftCave/DraftCaveOptimizer branch `production-ui-v1`, commit `e65dbe9`, into a private repository branch. The optimizer's CP-SAT solver search worker count was set to 1 *only in this isolated service* to make repeated seeded experiments reproducible. **The user's uncommitted local ZIP contains newer changes not deployed here.**

Inputs: official DraftKings 2026-11-15 main-slate salaries, 506 DK IDs; imported 2026-11-10 10 AM point forecasts. 256 positive projected eligible players, 249 zero-projection/absent rows plus one doubtful positive player withheld. Ownership and ceiling intentionally blank; this is not DC Points or DC Ownership.

No public backend access: all endpoints require a long secret value in `x-draft-cave-key`; secret must be in protected Vercel environment variables, never source code or `NEXT_PUBLIC_` settings.

Do not select entries by projection alone. No paid contests, production promotion or model claims from this engineering fixture.
