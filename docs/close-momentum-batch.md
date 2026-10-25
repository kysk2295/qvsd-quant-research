# Batch 2: close momentum
Registered 2026-10-25 before execution.
Primary implementation source: https://www.quantconnect.com/research/15348/intraday-etf-momentum/

The published implementation measures the first 30-minute close against the prior regular-session close, then takes that direction in the final half-hour. It references Gao et al. This independently written NQ port uses one futures contract and native next-bar market execution, not ETF portfolio allocation or market-on-close auction fills. Anchor=0 retains the prior-close reference; Anchor=1 is an explicit current-open modification. No stop or target is added.

Frozen grid: two anchors times native slippage 2/4 ticks, external assumed round-trip fee $5/$10. September 28 ET warms up prior RTH close; evaluation September 29–October 6 (six weekdays). Complete 390-minute RTH observations required for previous close; missing minutes disable entries. Prior session inferred from weekdays; not holiday-aware, so restricted to this named window. Native end-stamped fills can report 15:31 entry and 16:01 exit. Futures exit approximates ETF close; it is not an auction fill.

All dates are already examined diagnostic data. No independent holdout or optimization winner. Competition-hour eligibility is unverified, so this is a research benchmark only. Four runs maximum. No change based on outcome.

Recent-data gate: verified October 21 L1/L2 parquet exists. Research UI currently allows download, not Import; Bars reflection exposes no public Import member. Official text-import documentation is https://ninjatrader.com/support/helpguides/nt8/importing.htm . No database file was fabricated or overwritten. Recent NRD is not claimed as native historical coverage.

## Results

All four native runs completed. Six session audits each confirmed 390 contiguous RTH minute bars, no observed gap, and a ready signal. Each ledger had exactly the six declared ET dates, one contract per trade, TimeExit, 15:31 to 16:01 NT end-stamped execution bars. This is not an ETF market-close auction fill.

| Anchor | Trades | Base net | Stress net |
|---|---:|---:|---:|
| Prior RTH close | 6 | -$4,690 | -$4,840 |
| Current RTH open | 6 | -$3,030 | -$3,180 |

All settings fail the diagnostic. The prior-close signal was long on all six days; the open-anchor variant changed direction on two days, improving but not reversing the loss. No optimized winner and no inference that the published ETF findings are disproven. Full native output: ignored data/runner/close-momentum-batch2.json. Aggregates: research/close-momentum-summary.json. Compile check passed; installed reload retained the existing architecture warning.

## Recent tick preparation

research/prepare_nt_ticks.py creates Last-only UTC text at 100ns precision, selects only MarketDataType=2, validates order, positive size and quarter-point NQ prices, refuses destination overwrite and records hashes. October 21 output: 605,573 ticks, summed volume 650,814; independent text re-read matched both totals. It includes neither bid/ask snapshots nor L2. Not suitable for claiming bid/ask-aware Tick Replay validation.

File: ignored data/runner/nt-import/20261021/NQ 12-26.Last.txt. Not imported. Computer Use observed the Historical Data window and attempted to expand Import; click failed with coordinate input geometry is unavailable. Fresh window selection and screen capture then failed with FrameArrived timed out: timed out waiting on channel. No success or recent native coverage is claimed. Native historical import/readback remains the next data gate.
