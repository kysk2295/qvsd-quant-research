# RSI history repair and channel candidate

The preregistered batch budget was three date downloads, two linked RSI repairs at unchanged EntryLevel2 and six tests of one new channel hypothesis. No Cafe expansion, live orders, purchases or self-invocation occurred.

## History versus evaluation

New NQ Last ticks: October9 **400,643**, October11 **46,073**, October18 **60,610**; total **507,326**. All three NRD files decoded without corruption/truncation and native imports acknowledged the exact counts. These dates supply context, not new OOS performance. Evaluation remains the same nine RTH sessions October12–22; development remains the previously observed Sep29–Oct6. No genuinely future data has yet been evaluated.

The installed `CME US Index Futures ETH` trading-hours template defines Sunday17:00CT through Friday16:00CT, with daily16:00–17:00 maintenance. Its hash and holiday checks are in the coverage evidence. Across the required interval,158 scheduled five-minute intervals were previously absent: first-day warmup had114/200 observed intervals and October19 had128/200. After acquisition, **all2,486 required intervals are nonempty and each evaluation day has200/200 preceding intervals**. This verifies interval continuity, not lossless tick completeness, quotes or depth. Native strategy output independently confirms no remaining indicator-warmup blocks.

## Linked RSI results

The strategy source hash, evaluation inputs, order rules, sizing, stop and costs are unchanged. Only data history and requested history start changed (October11 → October8). Each new run retains the original run/key/hash through `supersedes` and correction evidence. Both versions remain available; they are not independent samples.

| Cost | Original net | Repaired net | Trades | Net without best winner |
|---|---:|---:|---:|---:|
| 2 ticks +$5 roundtrip | +$800 | +$800 | 6 | -$245 |
| 4 ticks +$10 roundtrip | +$770 | +$770 | 6 | -$270 |

The full trade ledgers are identical. On October12, the old run had77 warmup blocks; the repaired run instead records70 trend-filter blocks and7 entry-time blocks. This corrects the reason for inactivity without manufacturing new trades. Only four evaluation dates contain trades; development stress for the selected setting was -$1,390. Six trades, phase instability and dependence on the largest winner still justify **deferred**, not adoption or permanent rejection. Daily net, concentration, fee sensitivity and missing path-equity risk remain explicit in the assessment.

NinjaTrader prefetched earlier history than requested: the repaired native bars begin October7 07:05KST. The original preflight hashes are preserved. An additional post-execution full local-data hash and actual loaded windows were published, explicitly labeled post-execution. Future runner preflight now snapshots every local NQ minute file (plus ticks for High fills), covering automatic prefetch. This provenance improvement did not trigger duplicate tests.

## New channel hypothesis

[TradingView's public Channel BreakOut strategy](https://www.tradingview.com/support/solutions/43000599828-channel-breakout-strategy/) uses price-channel breakouts and stop entries. This is a distinct **close-confirmed RTH adaptation**: prior5 bars baseline or20 alternative, next-bar market orders, both directions, fixed48-tick stop, opposite-channel/ten-bar/time exit, one contract, maximum4 entries/day and the same daily entry halt. No ETH indicator history is needed for its same-session channel. It is not represented as an exact TradingView port.

| Phase / length | Trades | Base net | Stress net |
|---|---:|---:|---:|
| Development /5 | 24 | -$3,685 | -$4,620 |
| Development /20 | 13 | -$2,775 | -$2,950 |
| Recent /20, frozen | 28 | -$4,255 | -$4,395 |

Length20 was frozen by the predeclared development stress criterion; it was not selected using recent performance. These finite observations fail the after-cost performance criterion. No additional tuning was performed against the recent window.

## Evidence and follow-up

All **eight new native runs received dashboard ACKs**, including trade ledgers, daily metrics, assessments and next actions. Two RSI comparison updates and eight loaded-window evidence updates also received ACKs. Original results and metrics remain intact. Eight focused regression tests passed; the new strategy compiled and loaded in NinjaTrader. The worker finishes `idle` with no current run.

Keep RSI EntryLevel2 fixed. Next bounded historical extension can evaluate October7–9 after acquiring/auditing its required ticks and prior indicator context; classify it as additional observed-history research, not pristine OOS. Separately queue simulation-only strategy order/fill Replay, with a reviewed Playback-account guard and explicit execution comparison. Replaying existing trades cannot increase the statistical sample. Prospective simulated-forward evidence must use genuinely future dates after rule freeze and available data; none has run. Cafe candidates and their evidence tasks remain preserved at lower priority.

## Observed fill-cost limitation

The recent native2/4tick runs have identical entry and exit prices, both for RSI and channel. Thus the nominal recent base/stress net difference reflects assumed fees, not an observed incremental price penalty. [NinjaTrader documents that historical slippage is bounded by the next bar's high/low](https://ninjatrader.com/support/helpguides/nt8/understanding_historical_fill_.htm); the identical fills are direct evidence here, while attribution to the single-tick fill-bar constraint is an interpretation consistent with that documentation. Echoed settings alone do not establish realized friction.

Additional adverse-price sensitivity was computed **after observing this limitation**, separately from native metrics. It charges $5 per NQ tick, two fills per round trip and quantity, beyond the observed native fills. It is arithmetic sensitivity, not another simulation or an estimate of live slippage; trading decisions and original ledgers are unchanged.

| Scenario | RSI net | Channel net |
|---|---:|---:|
| Base native fills/$5 fee plus2 extra ticks per fill | +$680 | -$4,815 |
| Nominal stress fills/$10 fee plus4 extra ticks per fill | +$530 | -$5,515 |

The full2/4extra-tick matrix for both fee cases, with daily net and best-winner exclusions, is saved and published in `research/native-slippage-sensitivity-v2.json` (four ACKs). RSI under the latter scenario still becomes -$470 after excluding its best winner. This preserves the deferred assessment and makes execution Replay/forward validation relevant before any trading eligibility claim.
