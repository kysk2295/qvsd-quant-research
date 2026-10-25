# Batch 2: close momentum
Registered 2026-10-25 before execution.
Primary implementation source: https://www.quantconnect.com/research/15348/intraday-etf-momentum/

The published implementation measures the first 30-minute close against the prior regular-session close, then takes that direction in the final half-hour. It references Gao et al. This independently written NQ port uses one futures contract and native next-bar market execution, not ETF portfolio allocation or market-on-close auction fills. Anchor=0 retains the prior-close reference; Anchor=1 is an explicit current-open modification. No stop or target is added.

Frozen grid: two anchors times native slippage 2/4 ticks, external assumed round-trip fee $5/$10. September 28 ET warms up prior RTH close; evaluation September 29–October 6 (six weekdays). Complete 390-minute RTH observations required for previous close; missing minutes disable entries. Prior session inferred from weekdays; not holiday-aware, so restricted to this named window. Native end-stamped fills can report 15:31 entry and 16:01 exit. Futures exit approximates ETF close; it is not an auction fill.

All dates are already examined diagnostic data. No independent holdout or optimization winner. Competition-hour eligibility is unverified, so this is a research benchmark only. Four runs maximum. No change based on outcome.

Recent-data gate: verified October 21 L1/L2 parquet exists. Research UI currently allows download, not Import; Bars reflection exposes no public Import member. Official text-import documentation is https://ninjatrader.com/support/helpguides/nt8/importing.htm . No database file was fabricated or overwritten. Recent NRD is not claimed as native historical coverage.

