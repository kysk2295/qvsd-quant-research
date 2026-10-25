# Daily-session NR7 review and native functional validation

The [ChartSchool NR7 article](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7) defines daily range as high minus low and compares it with the preceding six days. It distinguishes Crabel's original opening-range entry from the article's prior-NR-day high/low breakout interpretation. The original book was not directly verified; a candidate PDF returned404. This study implements the published ChartSchool interpretation as an explicit NQ adaptation, not exact Crabel replication.

The adapted daily unit is a complete09:30–16:00ET NQ RTH session, not a full CME daily bar or seven intraday bars. Strictly narrower-than-all-six excludes ties. The next session's first qualifying minute close must be at least one tick beyond the previous day's boundary; entry is market after confirmation, at most once/day. A48tick research stop and15:55exit are added. No ATR/true-range substitute, intraday-seven-bar substitute or outcome-driven threshold change was used.

Fifteen completed sessions were reconstructed independently from preserved Last ticks. Seven sessions, Oct2–12, are warmup; eight sessions, Oct13–22, are evaluation. That is sufficient to calculate NR7 correctly for those eight dates, but does not imply adequate statistical evidence. **None of the eight evaluation dates had a qualifying prior-day NR7 setup.**

Before native execution, a coverage-contingent rule allowed skipping the second cost run if the first confirmed this absence. One NinjaTrader native HighTick1 run completed and exactly matched all15daily high/low/close records and all8prior-seven-session setup decisions. It produced zero signals and zero trades. Ten assertions against actual C#daily range/breakout/calendar math passed. Compilation and native session coverage passed. Entry, stop and exit behavior was not exercised, so execution correctness and friction are not established by this run.

The result is **condition absent / performance not evaluable**, not a profitable zero-drawdown strategy and not strategy-family failure. Both fee variants would have zero trades; the second native cost run was intentionally skipped. Native result and reviewed classification ACKs were confirmed. Full captured output and empty trade ledger are saved under `research/nr7-rth-*`.

## Bounded data work

The saved acquisition plan covers the nine adjacent preceding sessions Sep21–Oct1, with at most three download submissions per chunk and nine total; no native performance budget is granted by that data plan. Existing minute files are inventoried first, but presence does not prove RTH completeness or session convention. Missing/unverifiable sessions require real source data and390minute coverage checks.

If all context is valid, newly evaluable dates are Sep30,Oct1,Oct2,Oct5–9,Oct12. Previously evaluated Oct13–22 must not be repeated. The rule remains fixed, and any actual performance batch requires separate preregistration plus qualifying setup exposure. Even24completed context sessions would remain exploratory historical data, not independent future validation.

The OFI date-extension campaign remains closed, MACD is not rerun, and RSI/Bollinger evidence and follow-up tasks remain preserved. The finite worker ended idle. No live trade, purchase, Playback/order-control query or self-invocation was used.
