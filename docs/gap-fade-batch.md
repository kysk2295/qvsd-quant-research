# Opening-gap fade NQ exploration — October25,2026

Completed a new fixed hypothesis with two native NinjaTrader High Tick1 cost tests, full ledger review and dashboard ACKs. Twelve previously observed sessions produced nine shared trades, all stop exits. After-fee net was−$2,210 base and−$2,255 nominal stress. This setting misses the adoption criterion; nine trades are not a statistical rejection of every gap-reversal strategy. No parameter was changed after observing results.

Cafe sources were considered first: saved article10 concerns OR/IB concepts already studied, and its original page remained inaccessible. Existing close-momentum research was also checked and excluded as a duplicate. The selected source was the [public QuantConnect Fading the Gap lesson and solution](https://www.quantconnect.com/forum/discussion/10733/boot-camp-7-fading-the-gap-all-text-and-code/), reproduced by Greg Kendall and with a solution posted by Varad Kabade. It describes buying a large downside opening gap and exiting45minutes after open, scaled by60minute price standard deviation. The implementation here is independently written and does not reproduce the source's TSLA performance.

NQ adaptations were frozen before data scoring and execution: one-minute bars; prior complete RTH session's last60 minute closes; population standard deviation; current09:30 opening price versus prior16:00 close; strict delta<−3sigma; one-contract long after the09:31 completed bar;48tick protective stop;10:15time exit; at most one entry/day. The volatility snapshot excludes all current-day prices. The fixed October calendar requires the previous weekday, including Friday for Monday, and is not a general holiday calendar. A sigma multiple is not a probability or normal-tail confidence statement.

| Measure | Base | Nominal stress |
|---|---:|---:|
| Requested native slippage |2ticks|4ticks|
| Assumed round-trip fee |$5|$10|
| Trades / active sessions |9 /9|9 /9|
| After-fee net |−$2,210|−$2,255|
| Closed-trade drawdown |$2,210|$2,255|
| Additional4ticks per fill sensitivity |−$2,570|−$2,615|

Actual fill tuples were identical under2/4requested ticks, so nominal stress changed fees only. Additional adverse costs are a separate arithmetic sensitivity, not new native fills or estimated live slippage. Eight trades lost$240 before fees and one lost$245. A protective stop does not guarantee its distance as the maximum loss. No winner concentration claim is meaningful because there were no winners. Mark-to-market drawdown remains unknown.

All12 current sessions and their13 distinct current/prior RTH dates had390 observed minutes. NinjaTrader's prior close, opening price and prior60minute sigma matched independently aggregated Last ticks within1e−6 for every evaluation date, before the runner accepted results. Native output also confirmed390 contiguous RTH bars per session. Presence of observations does not prove lossless ticks or bid/ask completeness.

Ten assertions against the actual C# calculation helper checked strict thresholds, zero/nonfinite volatility, full-window requirements, population sigma and weekday boundaries. Eight existing protocol tests and scratch/native compilation passed. Nine qualified dates matched nine signals and nine one-contract long trades, with no duplicate date, same-day exits, correct entry/exit time bounds and exact PnL arithmetic. All exits were stops, so the native time-exit branch was not exercised. The new class explicitly permits only Historical Backtest-account execution.

Every attempted native run is preserved. Tracked manifest, coverage, results, compact native ledgers and summary are under `research/gap-fade-*`; full raw responses remain in local runner state with tracked hashes. The earlier Moving Momentum results were annotated and ACKed to distinguish its unmet sample adoption criterion from statistically inconclusive four-trade evidence; no metrics or trades were altered.

Next candidate: best-quote order-flow imbalance feasibility, based on [Cont, Kukanov and Stoikov's primary paper](https://arxiv.org/abs/1011.6402). Its contemporaneous price-impact evidence is not proof of profitable lagged NQ prediction. The backlog and work queue first require auditing real bid/ask sizes, ordering, stale/crossed quotes and coverage, followed by reading the full paper and preregistering any predictive rule before looking at that rule's PnL. OHLCV or Last-only imports cannot substitute for quote imbalance. No native tests for that next candidate are yet registered or executed.

RSI's frozen-rule future-data backlog is preserved. Playback remains blocked and was not retried or enabled. No live orders, purchases, self-invocation or policy bypass occurred. No background research process remains after this finite batch.
