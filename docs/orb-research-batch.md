# Public strategy research batch 1
Registered before results: 2026-10-25.
Source: [QC Boot Camp ORB lesson, reproduced by Greg Kendall](https://www.quantconnect.com/forum/discussion/10724/boot-camp-5-opening-range-breakout-all-text-and-code/).

Source rule: first 30 minutes define the opening range; a closing price outside it establishes direction; exit at 13:30 ET. Original uses TSLA and portfolio allocation. Independent NQ adaptation uses one contract, one trade/day, completed 1-minute bars and native next-bar fills, with no added stop/target. This is rule adaptation, not reproduction of original TSLA returns. Missing opening minutes or subsequent minute gaps disable new entries; audit output records observed bars.

Frozen comparison: RangeMinutes 30 (baseline), 15 and 60 (sensitivity). Native slippage 2/4 ticks; external assumed round-trip fees $5/$10. No parameter chosen after seeing results. Six whole-period native runs, September 28–October 6 ET, with September 28–October 2 and October 5–6 reported separately as chronological diagnostics. These dates have previously been examined: neither is an independent holdout. No statistically meaningful optimization selection with this sample. No live activation. An unprotected one-contract baseline may violate competition risk limits: diagnostic only.

Next candidate backlog: traceable VWAP reversion implementation; trend pullback; L1/L2 confirmation after data reconstruction. These are not implemented by this batch.

