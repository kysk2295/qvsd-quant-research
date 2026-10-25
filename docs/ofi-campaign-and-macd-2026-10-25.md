# Fixed OFI campaign closed; distinct MACD candidate evaluated

## Final OFI extension

Oct2 was separately preregistered as the last date in the current historical-extension campaign, with two native cost-condition runs and explicit cost/concentration stop criteria.497,185Last ticks passed validation and were imported by NinjaTrader. All390RTHminutes were present;383passed the unchanged quote-quality gate. All7exclusion reasons were independently recomputed using only information preceding each feature end, with no future outcome selection. Files and native sources are hash-pinned.

The new4trades returned+$150/+$130 after$5/$10roundtrip fees. Signal/feature/ledger comparisons and raw simulated execution timestamps passed. Existing14dates were not rerun. Across15historical sessions there are60unique OFI trades and10native cost runs, all for one fixed configuration. Cost variants do not duplicate the sample count.

| OFI aggregate | $5fee | $10fee |
|---|---:|---:|
| Net |+$465|+$165|
| Extra4ticks perfill |-$1,935|-$2,235|
| Best day excluded |-$3,345|-$3,625|
| Closed-trade drawdown |$4,385|$4,615|
| Additional adverse ticks perfill to zero net |0.775|0.275|

The preregistered stop criteria were met. Routine date additions for this fixed OFI candidate end here; the adoption gate is unmet. Reopening requires a distinct preregistered research question or data regime, not threshold tuning to these outcomes. This is not a statistical rejection of every order-flow hypothesis. All earlier evidence remains available.

## MACD cross adaptation

The distinct candidate follows the [official MACD strategy definition](https://www.tradingview.com/support/solutions/43000644943-macd-strategy/): histogram sign changes with12/26/9EMA defaults. Explicit NQ adaptations are one-minute RTHreset, first-close EMA seeds,80completed-bar warmup, flat-only entries rather than immediate reversal, maximum4trades/day,48tick stop, opposite-histogram/10bar/15:55exit and the existing realized-loss gate. Entries are10:50–15:25ET. This is not the earlier Stoch/trend/MACD composite, nor exact TradingView replication.

One configuration and two native HighTick1 tests were registered before outcomes on15already-observed historical sessions.60unique trades returned-$770/-$1,070; extra4ticks perfill gives-$3,170/-$3,470. Best-day exclusion gives-$2,620/-$2,900; closed-trade drawdown is$2,915/$2,995. This fixed candidate misses the adoption gate. No parameter search or repeat test is justified by this result.

Nine boundary/EMA assertions against the actual C#helper passed. Independent Python calculations matched all5,850native EMA/histogram/crossing rows perrun. Every minute close matched preserved raw Last-tick aggregation. Signals, directions, quantities, timing and price-derived PnL matched native ledgers. Full-precision simulated callback/Trade timestamps were retained; repeated cumulative daily print rows were deduplicated and do not count as new trades.

## Limits and next task

Both candidates' requested2/4tick native slippage produced identical actual fills. Nominal differences are external fees; extra ticks are separate arithmetic total adverse-cost scenarios. Do not subtract full spread again after replacing prices with bid/ask touch. Raw simulated timing is not live routing/queue evidence. Unrealized drawdown and exact real execution remain unverified. Every date in this report is historical/exploratory, not independent future validation.

Four new native results and four primary reviewed-metadata ACKs were confirmed; two further MACD metadata ACKs clarified the EMA-math label and raw timing field. The finite batch finished idle. RSI and Bollinger deferred candidates remain intact. Next queued work is one source/definition review of an NR7volatility-compression hypothesis, checking overlap with prior ORB/channel tests before any separately budgeted implementation. Its current native budget is zero. No Playback/order-control endpoint, live trade, purchase or self-invocation was used.
