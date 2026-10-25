# NQ validation cycle registered 2026-10-25

User requested data acquisition, GitHub/cafe strategy ports, chronological validation and Replay for survivors.

Research sources are the repository's existing cafe analysis (articles 5, 10, 17, 42) and `research/backtest.py`: opening-range breakout, retest, and failed initial balance. These are explicit research interpretations of discretionary ideas, not exact reproductions of every original author's rules.

Before new cafe runs: use NQ DEC26 only, one-minute native history aggregated by NinjaTrader to five-minute bars. Baseline OR=15 minutes, failed IB=60 minutes. A single alternative OR=30 is allowed for breakout/retest. Risk budget $300 per trade, max 1 NQ, up to four entries per day, stop new entries after realized daily loss $900. Base costs: native 2 ticks plus external assumed $5 round trip; stress: 4 ticks plus $10. Do not loosen sizing to force trades.

Development window: Sep 29–Oct 6 ET (already explored, short). Recent diagnostic window: Oct 19–23 ET, restricted to dates that pass raw-data checks. Choose parameters using development only; then freeze before recent evaluation. The old Yahoo analysis already examined Aug–Oct; neither window is a pristine independent holdout. True prospective validation remains future data after rule freeze.

Provisional Replay candidate gate: >=30 development and >=20 recent closed trades, positive net in both cost cases and both windows, recent stress profit factor >=1.2, no date/data/order errors, and no single trade contributing over half positive net. These are research screening thresholds, not statistical proof or competition eligibility. If no candidate passes, no strategy is promoted to Replay; a transport-only Replay check may separately test data/clock plumbing and must not be described as strategy-fill validation.

Official current competition hours and broker costs remain unverified. Report the six-month-data requirement as unmet unless actually acquired. Do not label a few recent days a complete market-regime study.

Initial data milestone: native TextImportType API imported 605,573 Last ticks for Oct 21 with UTC source, generated minute bars, no import errors. A one-day PublicORB plumbing probe produced one trade (+$3,250 before fees); that observation is diagnostic, not selection evidence. Explicit Tick Replay=false will be used for cafe OHLC testing; Last-only data cannot validate historical bid/ask behavior.

## Completed cycle and result

No strategy passed. Native historical engine: 10 development runs, 6 recent runs, then 6 higher-resolution robustness checks. One additional recent Variant 3 run was executed visibly in Strategy Analyzer. Its output independently confirmed four audited days, 12 sizing rejections and zero trades. The Analyzer remains on that result.

### Data

Oct 19 Replay was newly downloaded (200,454,204 bytes). Oct 19, 20, 21 and 22 L1 exports passed decoder/header checks; all four text files imported through NinjaTrader's own TextImportType API with UTC timestamps and minute generation. Total Last records: **2,595,775**. Each RTH date has trades in all 390 minutes, timestamps do not reverse, prices lie on the quarter-point grid and sizes are positive. This is not proof that every exchange tick is present. Oct 23 remains excluded: offline decoded values do not match header volume/range; native readability alone does not resolve that discrepancy.

Hashes, tick counts, RTH volume and missing-minute checks are in `research/recent-tick-audit-20261025.json`. Native recent bars loaded Oct 19 07:05 through Oct 23 06:00 KST; evaluated dates are **Oct 19–22 ET**, not Oct 23 ET. Development bars loaded Sep 28 07:05 through Oct 7 06:00 KST; six evaluated ET dates Sep 29, 30, Oct 1, 2, 5, 6.

The six-month requirement is **not met**. Only a short recent sample was added. No connected intraday provider is configured. A wider futures dataset and a genuinely prospective window remain necessary; these results do not qualify as an independent holdout test.

### Strategy and execution differences

`native/CodexCafeRange.cs` independently ports the repository's OR breakout, OR retest and failed-IB hypotheses. This is a documented research adaptation, not a claim of exact source parity: max quantity is one NQ; pre-submission risk estimate is `(signal-close-to-stop distance + 2 points) * $20 + $10`; protective prices use the completed signal bar rather than future entry prices; gap fills may exceed $300. The $300 budget is an inherited **research assumption**, not an official competition rule or user-approved live risk limit. Fees are external assumptions. Daily realized loss filter excludes external fees. No live strategy is enabled.

Native five-minute bars are end-stamped, signals use completed bars, and stop/target execution belongs to NinjaTrader. RTH gap checks block entries on missing bars. The AUDIT line occurs at 15:55 and therefore says 77 bars; the independent tick audit checks the full 390-minute session. Source/timeframe changes and discretionary original definitions prevent asserting exact Python/native equivalence.

### Results (after assumed fees)

| Variant | Development trades | Development base | Development stress | Recent trades | Recent base/stress |
|---|---:|---:|---:|---:|---:|
| OR breakout 15 | 0 | $0 | $0 | 0 | $0 / $0 |
| OR breakout 30 | 0 | $0 | $0 | Not selected | — |
| OR retest 15 | 1 | +$360 | +$345 | 0 | $0 / $0 |
| OR retest 30 | 2 | +$95 | +$55 | Not selected | — |
| Failed IB 60 | 4 | +$1,455 | +$1,375 | 0 | $0 / $0 |

Selection was frozen before recent cafe runs: baseline 15 for breakout (tie), 15 for retest, fixed 60-minute IB. None was eligible for promotion even before recent results. Recent rejected signal counts: breakout 6 (minimum estimated risk $1,020), retest 4 ($515), failed IB 12 ($345). Zero trades means untradeable under this budget, not evidence of a profitable or loss-free edge. Risk was not loosened to manufacture trades.

Positive development results are too sparse; the IB gross winning trade contributes more than its total net. Several trades share a primary five-minute bar. Six additional High/Minute/1 native fills checks retained the same trade counts and P&L. This does not establish tick-level fill realism. Effective cost/fill settings, session audits and trade dates were verified by `research/summarize_cafe_cycle.py`.

### Replay

No strategy survived screening, so **strategy-fill Replay validation was not performed**. A separate transport-only Market Replay job did run Oct 21 09:29–10:31 ET at requested 1000x, reached the exact target in 30.32 wall seconds, paused, and reported zero Playback101 executions and no warnings. Playback was then disconnected. Evidence: `research/replay-transport-20261025.json`. The research strategies intentionally only submit on the historical Backtest account; this transport check does not bypass that guard.

### Implementation validation and remaining work

Native source compilation and installed assembly reload passed with zero errors; an existing CS8012 architecture warning remains. Import API validates the prepared file hash, the existing futures instrument, approved research path, disconnected feeds and no account exposure. It invokes NinjaTrader's parser/storage implementation rather than writing proprietary database files. GUI strategy switching uses the actual ShortTypeName property; merely changing SelectedText was tested, found insufficient, restored and removed from the action implementation.

Next meaningful research: acquire a substantially longer native dataset, implement other source hypotheses that can fit NQ risk constraints (or pre-register a different research risk budget), and accumulate new forward observations after rule freeze. Do not tune repeatedly against Oct 19–22 or present these rejected candidates as a completed competition-ready system.
