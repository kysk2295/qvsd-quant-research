# Public strategy research batch 1
Registered before results: 2026-10-25.
Source: [QC Boot Camp ORB lesson, reproduced by Greg Kendall](https://www.quantconnect.com/forum/discussion/10724/boot-camp-5-opening-range-breakout-all-text-and-code/).

Source rule: first 30 minutes define the opening range; a closing price outside it establishes direction; exit at 13:30 ET. Original uses TSLA and portfolio allocation. Independent NQ adaptation uses one contract, one trade/day, completed 1-minute bars and native next-bar fills, with no added stop/target. This is rule adaptation, not reproduction of original TSLA returns. Missing opening minutes or subsequent minute gaps disable new entries; audit output records observed bars.

Frozen comparison: RangeMinutes 30 (baseline), 15 and 60 (sensitivity). Native slippage 2/4 ticks; external assumed round-trip fees $5/$10. No parameter chosen after seeing results. Six whole-period native runs, September 28–October 6 ET, with September 28–October 2 and October 5–6 reported separately as chronological diagnostics. These dates have previously been examined: neither is an independent holdout. No statistically meaningful optimization selection with this sample. No live activation. An unprotected one-contract baseline may violate competition risk limits: diagnostic only.

Next candidate backlog: traceable VWAP reversion implementation; trend pullback; L1/L2 confirmation after data reconstruction. These are not implemented by this batch.

## Executed results

All six native jobs completed. Seven ET dates: September 28, 29, 30, October 1, 2, 5, 6. Each run emitted seven session audits, each with 240 consecutive minute bars through the 13:30 signal time and the required opening-range count. Every trade was one contract, entered after its opening range, exited via TimeExit on the same ET date, and closed no later than 13:31 (NT end-stamped execution bar). Full JSON remains in ignored data/runner/public-orb-batch1.json. Aggregate results are versioned in research/orb-batch1-summary.json.

| Opening range | Trades per run | Base net | Stress net | Base earlier / later |
|---|---:|---:|---:|---:|
| 30 minutes, source baseline | 7 | -$9,090 | -$9,260 | -$8,845 / -$245 |
| 15 minutes | 7 | -$7,325 | -$7,495 | -$7,325 / $0 |
| 60 minutes | 7 | -$10,075 | -$10,235 | -$9,270 / -$805 |

Native standard-fill settings were read back; assumed fees were subtracted from each native trade. Compilation passed with no errors (one preexisting architecture warning on installed reload). No synthetic fills or Python proxy prices were substituted.

Decision: all three unprotected NQ adaptations fail this diagnostic. Large losses exist before fee stress; a parameter-only cost fix is not supported. Seven observations per setting are insufficient to conclude that all ORB approaches fail. A protective-stop adaptation would be a NEW hypothesis, not a repaired original or a newly independent test. Do not designate the least negative setting as an optimized winner.

Remaining gates: longer native historical coverage including recent October sessions; independent evaluation data; native tick-resolution execution comparison; formal competition rule mapping. Replay NRD files must be converted/imported through a verified path before treating them as historical Strategy Analyzer inputs. This batch neither uses L2 nor validates an order-flow strategy. No repeating schedule was created.
