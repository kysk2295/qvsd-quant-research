# Fixed RSI historical extension — October 25, 2026

Two new NinjaTrader native High Tick1 backtests evaluated October 7–9 with EntryLevel2 unchanged. Both completed with zero trades and zero net PnL; both result submissions and subsequent metadata updates received dashboard ACKs. Zero trades is insufficient performance evidence, not a profitable or losing result. No completed historical request was repeated.

The preregistered manifest fixed three evaluation dates, two cost settings, warmup requirements, and no parameter search. October9 had already been inspected as context for a later window. These are historical extension sessions, not independent OOS. Combined with the October12–22 evaluation, the observed period now covers12 sessions but still only6 trades. Development losses remain part of the evidence.

October7/8 Replay files were downloaded using the observed native Historical Data window. The dedicated download helper rejected ambiguous duplicate window titles before submitting a download; targeting the already observed window resolved this. Both new files decoded without corrupt/truncated flags. Imported Last ticks: October6 436,946; October7 467,876; October8 636,076. October9 was already present. Native import completion records are saved.

All three evaluation sessions contain390 RTH minutes. The scheduled ETH audit covered830 five-minute intervals with zero missing intervals and200 preceding intervals for each open. Native output confirmed78 RTH bars per day, no gaps and no indicator-warmup exclusions. Interval presence does not establish lossless tick or bid/ask completeness.

| Session | Trend-filtered bars | RSI-filtered bars | Time-filtered bars | Entries |
|---|---:|---:|---:|---:|
| October7 |57|13|7|0|
| October8 |67|3|7|0|
| October9 |70|0|7|0|

The same counts occurred under both cost settings; these are the same three sessions, not six independent observations. Nominal2/4tick costs and additional arithmetic fill-cost sensitivities all yield zero because there were no trades. No fill realism can be inferred from this batch.

Playback strategy execution remains unverified. Health reported the simulation order module disarmed. The installed historical RSI strategy refuses non-Backtest accounts. A proposed read-only order-status query was rejected by automatic approval review with only `blocked by policy`; it did not execute, and no alternate access was attempted. Exact restart requirements and a one-session execution comparison plan are saved in `research/rsi-playback-preflight.json`. No live or simulated orders were placed in this batch.

Evidence: `research/rsi-extension-oct7-9-manifest.json`, `research/rsi-extension-oct7-9-coverage.json`, `research/rsi-extension-oct7-9-results.json`, `research/rsi-extension-oct7-9-ledgers.json`, and `research/rsi-extension-oct7-9-summary.json`. Full raw native responses remain in the local runner state; compact native settings, audit output and empty trade ledgers are tracked in Git.

Validation:8 existing protocol tests passed. The faster per-minute timestamp cache reproduced every previously saved tick-audit row exactly. Original strategy code and its installed hash were unchanged.

Next action: retain RSI as deferred; do not retune or repeat observed windows. Prioritize a distinct public hypothesis while reserving new post-October25 data for fixed-rule forward validation. Resume Playback only through permitted simulation controls after its documented prerequisites are satisfied. No background research process remains after this finite batch.
