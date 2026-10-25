# Three-session extension and a new RSI2 hypothesis

## Frozen scope

Acquire October12,13,14 NQ DEC26 Replay using the existing permitted route; validate headers, convert Last ticks, import into NinjaTrader and audit full RTH. Run three unchanged Cafe configurations at two fixed costs per day: 18 native tests maximum. Do not repeat October15/16 or completed Doji tests. If all three sessions remain inactive, pause blind Cafe date expansion and prioritize a new explicit candidate while retaining the evidence-completion backlog. Each date has a preregistered manifest.

Cafe strategy changes add diagnostics only. The original short-circuit return order and order logic remain unchanged. New counters expose range building, gaps, pending/held positions, ATR warmup, time cutoff, daily/entry limits, qualified patterns, risk-cap/too-close stops, reward-risk filter and entries. Qualified patterns overlap their outcomes; they must not be summed as separate rejected bars. At the 15:55 audit, exclusive counts must reconcile to 76 earlier bars and qualified patterns must reconcile to their four outcomes. Earlier logs do not contain this detail and are marked unknown rather than inferred.

## New public-rule candidate

[ChartSchool RSI(2)](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2) describes short pullbacks within a trend, using a long moving average, short RSI and a short moving-average exit. Its examples concern daily stocks. This research tests an explicitly different NQ intraday implementation, not a reproduction of Connors' published results.

`CodexRsiPullback`: 5-minute supplied ETH bars for RSI2/SMA200/SMA5; RTH-only long entries with price above SMA200 and RSI below5 baseline or below2 alternative. Minimum200 indicator bars, next-bar market entry, fixed48-tick stop from entry, SMA5/ten-bar/time exit, one contract, maximum4 entries per day and daily loss entry halt. Stop and intraday restrictions are adaptations. The source-derived idea is not evidence of NQ profitability.

Four development runs on Sep29–Oct6 select the best stress net (tie baseline5), followed by two frozen recent diagnostics on the nine available sessions Oct12–22. Base2 ticks/$5 and stress4 ticks/$10 assumed roundtrip. All parameters, risks, coverage policy and the six-run budget were recorded in `research/rsi-pullback-manifest.json` before testing. Older or already researched dates are not independent chronological OOS. A positive short sample would remain deferred, with session dependence and prospective evidence still outstanding.

## Data correction lineage

Simple repeated date/configuration requests remain blocked. A documented quality repair may be reevaluated only with an explicit reason, hashed evidence file, matching prior terminal acknowledged run keys/data hashes, changed data hash and unchanged strategy source. New runs preserve `supersedes` links and the correction evidence; no original result is overwritten. Uncertain submissions and strategy-retuning attempts cannot use this exception. This batch does not invoke the exception.

## Completed evidence

All three NRD files passed decode validation with no corruption/truncation. Native imports: Oct12 434,499 ticks, Oct13 462,251, Oct14 719,704; total **1,616,454** additional Last ticks. All three RTH sessions have390 observed minutes and no missing minutes. Acquisition manifests retain source/output hashes and exact native import point counts.

Cafe **18/18** native tests completed with dashboard ACKs and zero trades. Across three distinct sessions, base-cost observations show qualified patterns2/1/2 for OR15/OR30/IB60; all were blocked by the risk cap. There were no gap, ATR-warmup, pending-position, daily-loss or reward-risk rejections in these instrumented runs. Other bars were range building, outside the entry window, or lacked a qualified pattern (including trend checks). Pattern counts across configurations are not independent market events. Counter partitions reconciled to76 pre-audit bars per configuration/session.

The evidence supports current-constraint inactivity, not proof that the strategy can never work. Original positive1–4-trade results and all evidence tasks remain preserved. After five consecutive added sessions Oct12–16 without entries, further blind one-day expansion is deferred; the next priority is the new candidate's data-history problem. This matches the three-session batch's predeclared stop policy. Updated follow-up metadata received18 further ACKs without changing original metrics or terminal statuses.

RSI **6/6** native tests completed and received ACKs:

| Phase / EntryLevel | Trades | Base net | Stress net |
|---|---:|---:|---:|
| Development /5 | 10 | -$2,550 | -$2,700 |
| Development /2 | 8 | -$1,260 | -$1,390 |
| Recent /2 frozen | 6 | +$800 | +$770 |

Recent profit does not justify adoption. It was concentrated in one winner: largest-trade share of net130.6% base/135.1% stress; without that winner, net is **-$245/-$270**. Only four dates had trades. Oct12 recorded77 indicator-warmup blocks before its end-of-day audit, so the first recent session was not fully entry eligible. The actual loaded window starts October12 13:05 KST; native output warns that a data provider would be needed to fetch missing bars. Full RTH data therefore does not establish sufficient pre-window or complete ETH history for the SMA200. All metrics remain observed diagnostics; no independent OOS or Replay eligibility is claimed.

The next action is to obtain and audit earlier ETH indicator history, including at least200 complete five-minute warmup bars before the first evaluated session, then preregister a versioned data-coverage reevaluation without retuning EntryLevel2. Original raw runs, trade ledgers, metrics and assessment history must remain accessible. Broad date expansion, concentration, phase instability and genuinely unseen future evidence remain separate validation needs.

All six RSI native trade ledgers and cost-adjusted closed-trade equity curves were published; coverage limitations and next actions also received six metadata ACKs. Dashboard frontend files were not changed. Six regression tests passed, including the documented-correction exception, unchanged-data and retuned-code rejection, and preservation of old records. NinjaTrader compilation and assembly loading succeeded. The finite worker finishes idle with no current run; it does not self-invoke.
