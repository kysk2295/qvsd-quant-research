# Results dashboard review — 2026-10-25

1. Existing result list: archived proxy reruns and superseded transport records mixed with current NQ calculations. Wide sidebar and decorative sections obscured the result list. Captured /tmp/quant-audit/before.png.
2. Updated results: removed sidebar, decorative copy and aggregate total/completed cards. Current runner cases shown by default; archive checkbox restores all history. Worker idle is distinct from active experiments. Invalid date-window P&L excluded from table comparison; raw diagnostic values retained in details with warning. Reasons are visible in the table. Operational events collapsed.
3. Verification: server suite 6 passed, JS syntax check and five classification assertions passed. Production visual and interaction checks performed after deployment. Screenshots demonstrate layout only, not full accessibility compliance; focus outlines and native labels retained.

## Investigation evidence

Windows branch e1d120f report: 20 Python calculations on previously examined Yahoo data, 4 native calculations rejected for coverage, 29 superseded records, 5 blocked native cases, 1 blocked order-flow study. 59 records are not 59 validated strategies. No accepted strategy.

NT Playback clock and Windows local timezone differ. Bridge timezone comparison is unsuitable; this alone does not prove the displaced start-date cause. Adapter exact endpoint comparison also needs to distinguish warmup bars from evaluation trades. Windows instructed to investigate both before further grids. Order-flow implementation, independent walk-forward and new-data paper forward are not delivered yet.

Graphify update remains unavailable: its Python 3.12 interpreter path is missing.
