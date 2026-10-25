# Frozen Cafe extension: October 15

The next previously missing NQ DEC26 Replay day was downloaded through NinjaTrader Historical Data. NRD decoder reported no corruption, truncation, failure or empty output. Conversion yielded 714,544 Last ticks; native importer acknowledged exactly 714,544 points. RTH coverage has all 390 minutes and no missing minutes. Acquisition evidence and hashes are in `research/acquisition-20261015.json`; this does not include bid/ask or depth validation.

Before native execution, `research/cafe-extension-manifest-20261015.json` froze sources, rules, risk, expected frequency, session-based coverage assessment, six-run budget and the historical-extension role. October15 is earlier than already examined dates, so it is not independent chronological OOS. No original Cafe parameters were optimized or changed.

| Frozen configuration | Base / stress trades | Base / stress net | Evidence |
|---|---:|---:|---|
| Variant2 OR15 retest | 0 / 0 | $0 / $0 | One size rejection in each cost case |
| Variant2 OR30 retest | 0 / 0 | $0 / $0 | No entries; no size rejections logged |
| Variant3 IB60 | 0 / 0 | $0 / $0 | No entries; no size rejections logged |

All six executed in the native historical engine with High Tick1 fills, 5-minute signal bars, Tick Replay disabled, commission disabled in the engine and explicit external assumed fees. Base is two slippage ticks plus $5 round trip; stress is four ticks plus $10. The strategy audit shows 77 consecutive bars at its 15:55 reporting point, with no gap; independent tick coverage includes the full 390-minute session. Raw native responses remain local; the compact results and settings audit are versioned. All six dashboard POSTs received ACKs.

These are successfully completed calculations, not accepted strategies. OR15 is condition_mismatch; OR30 and IB60 are deferred. No trade-level performance inference is possible. October15 and October16 add two distinct sessions; twelve cost/configuration runs do not add twelve independent sessions. Prior positive 1–4-trade results remain preserved.

The extension runner now requires an explicit dated manifest and six frozen configuration/cost combinations. It refuses a prior same-date/configuration request even when its fingerprint changes, including uncertain earlier submissions. Five focused tests pass, including that duplicate-submission regression. Existing October16 and Doji experiments were not rerun.

Worker lifecycle is persisted in `research/worker-lifecycle.json` and published through heartbeat. The batch ended with phase `idle`, current_run null, and an explicit no-background-research message; it is not an always-on research process. No static frontend files were changed. Queue and backlog point to October14 acquisition → coverage audit → another frozen historical extension; longer-session coverage and future order/fill Replay remain pending.
