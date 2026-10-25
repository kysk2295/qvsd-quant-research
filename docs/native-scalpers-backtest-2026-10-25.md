# Native NinjaTrader strategy backtests — 2026-10-25

Executed installed CodexThreeScalpers variants 1–3 using NinjaTrader's Backtest account and native historical engine. This is not a Python price-proxy backtest or live trading. These are existing price-based research variants, not newly validated L2 strategies.

Evaluation: October 6, 2026, US Eastern morning. NQ DEC26, one contract, 1-minute primary bars, Tick Replay explicitly false, Standard fill resolution. TestDate=20261006 filters trading to that date. No optimization performed.

| Variant | Trades, base/stress | Base net | Stress net |
|---|---:|---:|---:|
| 1 multi-filter | 2 / 2 | -$830 | -$860 |
| 2 regime | 6 / 6 | -$1,195 | -$1,275 |
| 3 VWAP | 8 / 8 | +$205 | -$135 |

Base: native slippage 2 ticks, then assumed $5/contract round-trip fee deducted externally. Stress: native slippage 4 ticks, then $10 fee. Native commission was explicitly disabled; these fees are assumptions, not a configured broker commission schedule.

Native jobs b2–b7 completed. Effective fill settings and all trade timestamps were checked. All entries/exits are on October 6 ET, between 09:38 and 10:24 across the six runs. Loaded bars were October 5 07:01 through October 7 06:00 Korea time, including warmup. The API requested October 6–7 local dates; that entire two-calendar-day range is NOT claimed as covered. The strategy's explicit October 6 ET evaluation window is covered.

Playback was disconnected. The earlier SMA control now loaded September 28–29 instead of September 30–October 2; this supports Playback interference as a contributor but does not establish all general date-loading issues fixed.

The VWAP variant has same-minute entry/exit fills. Standard OHLC fill sequencing is insufficient evidence for a scalping edge; it also becomes negative under stress. No candidate is approved. Further gates: higher-resolution fills with verified tick history, more sessions, competition risk rules, and untouched evaluation data. Downloaded .nrd Market Replay files are not automatically Strategy Analyzer historical tick data.

Full native trade ledgers and settings: ignored local data/runner/native-scalpers-20261006.json. Installed source was read before running; source hash is saved alongside this report locally. No strategy source was modified.

