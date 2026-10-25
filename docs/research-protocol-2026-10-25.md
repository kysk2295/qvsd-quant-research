# NQ research and evidence completion

## Applied changes

New candidate execution requires a manifest containing source, hypothesis, exact rules, data requirements, expected frequency, metrics, costs, risk, bounded search, chronological role, coverage and stop policy. This gate does not retroactively make older tests preregistered. A new candidate without its manifest fails before submission. Source/data/request fingerprints prevent duplicate historical reruns; uncertain submissions require inspection.

Deferred and no-trade condition mismatches create durable, deduplicated data-extension → coverage-audit → re-evaluation tasks in `research/evidence-work-queue.json`. A completed one-day acquisition does not satisfy the remaining long-history task. Each stage must retain its evidence. Distinct native sessions, not repeated cost variants or fills, count toward coverage.

Cafe extension rules were frozen in `research/cafe-extension-manifest.json` before six new tests. Rare OR retests observed 1 or 2 trades in six sessions; failed IB observed four. A universal trade-count pass is inappropriate. The next collection target is 60 complete sessions, with rare candidates remaining inconclusive if uncertainty persists. Counts alone never confer eligibility. Session-block inference and dependence diagnostics remain future work once adequate sessions exist; no confidence interval has been fabricated. Historical thresholds in older runs are retained as legacy evidence, not newly preregistered gates.

## Actual data and native tests

NQ DEC26 October 16 Replay file decoded without corruption or truncation. Last-only conversion produced 691,212 trades, SHA256 `3042c2ac4da24565d677d95704a4001552be82792fa91a332a105c74e3923579`. NinjaTrader native import reported done with 691,212 points. RTH audit covered all 390 minutes. Quote and depth streams were not imported; this is insufficient to validate order-book hypotheses.

Frozen Variant2/Range15, Variant2/Range30 and Variant3/Range15 (internally IB60), each at 2-tick/$5 and 4-tick/$10 assumed round-trip costs, ran through the native historical engine with High Tick1 fills. All six produced zero trades. Retests reported size rejections; IB had no entries. All six results received dashboard ACKs. This adds one complete session, not six independent observations. October16 precedes already observed October19–22; it is historical expansion, not a clean chronological OOS test.

Existing Cafe records: 22 reassessed and acknowledged, 12 positive low-sample records deferred. Original metrics and terminal statuses were preserved. Ledger-derived evidence includes daily net with audited zero-trade dates, largest winner share, top-three positive contribution, net excluding best one/three positive trades, and an extra-fee sensitivity calculation. Missing unrealized equity risk is explicitly null. Native slippage variants remain separate observed runs; fee sensitivity is arithmetic, not simulated adverse fills.

## Dashboard compatibility

`status` remains calculation lifecycle; new successful calculations use `completed`, even when the research decision is deferred. Existing terminal `rejected` values are preserved for server compatibility. Research disposition is `params.assessment.decision`: `deferred`, `condition_mismatch`, `performance_fail`, `execution_error`, or `further_validation`. Consumers should show `reason`, `next_action`, `coverage_policy`, `concentration`, `ledger_evidence` alongside disposition. `completed` does not mean approved for trading. The Mac-owned frontend is unchanged; ACK proves storage, not that the UI already renders the new fields.

## Next evidence

Acquire additional permitted historical/Replay sessions, audit them, freeze the data role and manifest before results, and evaluate unchanged Cafe settings. Exact originals unavailable from cafe pages remain source-blocked; do not invent source parity. Daily-equity ConnorsRSI needs a separately justified NQ adaptation and longer history before execution. Any eligible strategy then needs actual order/fill Replay and prospective simulated-forward evidence. Playback clock movement alone is not strategy Replay validation. No current candidate is approved.

This is a bounded batch runner, not a self-invoking or continuously running AI service. The persisted queue is the next task's starting point.
