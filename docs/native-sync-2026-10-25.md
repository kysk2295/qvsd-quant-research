# Preserved native result synchronization

Published 16 previously executed diagnostics: scalpers 6, public ORB 6, close momentum 4. Each was serialized into runner telemetry and acknowledged by POST /api/runs; ack hashes are persisted in the existing queue control table. No experiment was re-executed or enqueued, and earlier invalid results retain their original IDs. Terminal snapshots have deterministic identity from native strategy, inputs, times, settings and ledger, avoiding collision when native job counters reset.

Runtime dataset hashes were not captured for these manual calls. They are explicitly unavailable; retrospective current-store hashes and observed source hashes are separate metadata, not claimed execution-time fingerprints. All records retain minute-bar diagnostic, NQ adaptation, no independent OOS, no Market Replay, and no UI reproduction limitations. Actual evaluation-window audits do not establish the whole requested calendar range is complete or fix all previous date-loading errors.

The server acknowledged all 16. Browser readback /api/state requires a browser session; the worker credential does not grant that access (unauthenticated GET returned 401). Do not equate ACK with visual dashboard inspection.

Extended native research control to open/read/render Strategy Analyzer. Existing action restrictions are unchanged; arbitrary Analyzer execution is not enabled. Full partial-source compile passed, installed source was backed up, reload confirmed. Opened Strategy Analyzer and read its settings and empty performance grid. Same-setting UI execution and comparison remain incomplete. This is window visibility progress only, not reproduced backtest results.
