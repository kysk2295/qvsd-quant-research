# Fixed OFI extension: newly acquired Oct5 historical session

Two preregistered native runs evaluated Oct5 only. No existing13session OFI window was repeated. The rule remains threshold10, completed-feature lag60seconds,5bar exit,48tick stop, one contract and4entries/day. The source has a separate frozen feature hash and additional raw simulated execution/Trade timestamp prints; trading rules were not retuned.

420,567original Last ticks passed ordering, price, size and full390minute RTH coverage checks, then NinjaTrader's guarded native text importer confirmed the same number of imported points. Quote features contain390minutes,367eligible and23excluded. Exclusion reasons were independently recomputed from each minute's quote groups and strictly preceding boundary quotes, matching all390eligibility flags. Reasons and exact source/end timestamps are preserved in `research/ofi-oct5-exclusions.json`. No subsequent price return or PnL entered the filter; whole-file consistency remains an offline data gate, not a claim of online completeness.

The4new trades returned-$990 after$5roundtrip fees and-$1,010 after$10fees. Native requested2/4tick slippage produced identical fills. All signals matched frozen features; quantities, side, causal timestamp separation and native price-derived PnL passed. Raw simulated entry/exit timestamps are retained, and all8timestamp/price pairs match original Last events. One entry's strictly prior spread was5ticks although the signal feature passed its historical<=4tick gate. This is preserved as an execution limitation, not used to change the rule after outcomes.

| Combined14historical sessions,56unique trades | $5fee | $10fee |
|---|---:|---:|
| Net |+$315|+$35|
| Additional2ticks perfill |-$805|-$1,085|
| Additional4ticks perfill |-$1,925|-$2,205|
| Excluding best day |-$3,495|-$3,755|
| Closed-trade drawdown |$3,885|$4,105|
| Additional adverse ticks perfill to break even |0.5625|0.0625|

Each cost condition repeats the same56trades; it does not create112independent observations. Total OFI native attempts are8across one configuration, two chronological initial segments and two one-day extensions. The separate Bollinger clock diagnostic is excluded. These are historical exploratory observations, not prospective or independent OOS. OFI remains deferred for cost and concentration; no family-wide statistical rejection is claimed.

HighTick1 uses Last-based simulated fills, not a bid/ask queue model. Raw time precision is not measured live routing latency. Strict-prior quote observations exclude same-timestamp groups whose relationship to simulated execution is unknown. Incremental adverse-tick scenarios are separate arithmetic; full spread must not be charged again after replacing fill prices with bid/ask touch. Unrealized path drawdown is not established by this closed ledger.

Two result ACKs and two reviewed-metadata ACKs were confirmed. A separate bounded next-data task permits exactly one download and one quality audit for Oct2, with zero native tests until a new preregistration. Existing RSI and Bollinger candidates remain unchanged and deferred. No Playback/order endpoint or live operation was used.

The Oct2 acquisition subsequently completed in that one-download/one-audit budget. The original158,438,783byte NRD decoded without truncation or integrity errors. All390RTHminutes contain quotes;383pass the same quality gate, with zero settled crossed groups. No Oct2 strategy outcome was evaluated. Two additional metadata ACKs published the acquisition evidence. The next pending task is Oct2 Last-tick coverage/import and separate fixed-rule preregistration; the worker is idle after this finite batch.
