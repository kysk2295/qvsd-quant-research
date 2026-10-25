# Moving Momentum NQ exploration — October25,2026

Implemented one new fixed strategy, compiled it against NinjaTrader, and completed two native High Tick1 backtests. Both runs and their reviewed metadata received dashboard ACKs. This setting is rejected for the observed sample: after-fee net was −$35 base and −$55 nominal stress. These are four shared trades under two cost conditions, not eight independent trades.

The local GitHub cafe report was reviewed first. Articles9/27 contain discretionary EMA/order-block descriptions; direct source retrieval was unavailable. This batch instead uses the explicit public [ChartSchool Moving Momentum framework](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/moving-momentum): moving-average trend, stochastic pullback, then MACD-histogram confirmation. It does not claim to reproduce the cafe author's strategy or daily-stock results.

The preregistered NQ adaptation uses five-minute ETH indicators, SMA20/150, slow stochastic K(14,3), and MACD(12,26,9). An eligible RTH pullback arms a directional setup; confirmation must occur on a later bar within six bars, with unchanged bias. Setup age never refreshes while armed. It resets on expiry, bias change, position, risk limit, gap or time-window boundary. Entries use one contract, a48tick stop, ten-bar/opposite-histogram/time exit, maximum four entries per day, and a fee-adjusted realized−$900 entry halt. The strategy explicitly accepts only Historical Backtest-account execution.

No parameter optimization occurred. October7–22 contains12 previously observed sessions; all results are exploratory, with no independent OOS claim. Three descriptive chronological segments were fixed in advance and were not used to choose settings.

| Measure | Base | Nominal stress |
|---|---:|---:|
| Requested native slippage |2ticks|4ticks|
| Assumed round-trip fee |$5|$10|
| Trades / active sessions |4 /3|4 /3|
| After-fee net |−$35|−$55|
| After-fee profit factor |0.953|0.927|
| Closed-trade drawdown |$740|$755|
| October7–9 net |$0|$0|
| October12–16 net |+$705|+$700|
| October19–22 net |−$740|−$755|
| Additional4ticks per fill sensitivity |−$195|−$215|

Actual entry/exit price tuples were identical under the requested2/4tick settings. Their net difference is therefore fees only. Additional adverse fill costs are arithmetic scenarios applied beyond native fills, not another native execution result or a live slippage estimate. Unrealized drawdown is not reconstructible from the closed-trade ledger.

Data audit:3,314 scheduled ETH five-minute intervals, zero missing;200 preceding intervals before every evaluation open;390 RTH minutes and78 native five-minute bars per session. No native warmup exclusions or order errors. Interval presence does not prove lossless tick data. The native loaded window was October5 07:05 through October23 06:00 Korea time; the explicit strategy dates restrict evaluation to the registered12 Eastern sessions.

Validation included13 assertions against the actual C# setup-state helper, eight existing Python protocol tests, successful scratch/native compilation, and runtime trace auditing. Each native run produced820 eligible trace rows:32 armed setups,19 expiries, five bias invalidations, and four confirmations matched one-to-one to four entries. Four other setups ended at eligibility boundaries. Checks verified causal age/crossing conditions, direction, one-contract size, entry timestamps within the next five-minute bar, non-overlap, and PnL arithmetic. All native entries were long; short-side setup boundaries passed synthetic tests but native short fills were not exercised in this sample. One stop filled one tick beyond its48tick distance, illustrating that a stop distance is not a guaranteed loss bound.

Evidence files: `research/moving-momentum-manifest.json`, `research/moving-momentum-coverage.json`, `research/moving-momentum-results.json`, `research/moving-momentum-ledgers.json`, `research/moving-momentum-trace-audit.json`, `research/moving-momentum-native-cost-comparison.json`, and `research/moving-momentum-summary.json`. Full native responses are also retained in local runner state; hashes are recorded in the tracked audit. No purchases, live orders, Playback orders, module activation, policy retries or self-invocation occurred.

Next action: retain this failed fixed setting without retuning it on the observed window; review a distinct public hypothesis. RSI remains deferred and reserved for new-data fixed-rule validation. Playback remains blocked under the previously recorded policy/module conditions; it was not retried. There is no running background research process after this finite batch.
