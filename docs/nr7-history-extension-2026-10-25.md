# NR7 historical extension — 2026-10-25

Completed a fixed-rule NinjaTrader Backtest batch, with no optimization or repeat of the original October 13–22 window.

## Data and preregistration

- September 23–25: three bounded downloads, one submission per date. Strict NRD decoding passed; each full RTH session has 390 occupied minutes. RTH Last counts: 389,461 / 449,995 / 390,215. UTC Last text retained 100ns precision and was imported through NinjaTrader's native importer.
- September 28–October 1: one previously completed, order-free native data collector verified four complete 390-minute sessions. This source is native minute history, not an independent raw-tick reconciliation.
- Seven consecutive preparation sessions: September 23, 24, 25, 28, 29, 30, October 1. No missing session was skipped. September 21–22 were unnecessary for this window.
- Seven historical evaluation sessions: October 2, 5, 6, 7, 8, 9, 12. These dates were previously observed for other candidates and are not independent OOS.
- Manifest and context were saved before native outcomes. Maximum two runs, one rule configuration. The C# extension changes only the class/helper names and earliest preparation date; entry, stop, and exit rules are unchanged.

## Native results

| Setting | Trades | After assumed fee | Additional 4 ticks per fill |
|---|---:|---:|---:|
| 2 ticks; $5 round-trip fee | 1 | -$245 | -$285 |
| 4 ticks; $10 round-trip fee | 1 | -$250 | -$290 |

Both native fill tuples are identical. The $5 difference is the fee assumption, not demonstrated execution deterioration. Additional friction is arithmetic sensitivity, not another fill simulation. Cost variants represent one unique trade.

October 7 was the only qualified session. One short entered at 31,244 at 09:31:00.084 ET and stopped at 31,256 at 09:31:08.420 ET: 48 ticks, -$240 gross. These are historical simulated timestamps. The stop branch was exercised; the time-exit branch was not.

All 14 native daily records and seven setup records matched frozen context. The first eligible minute-close breakout matched independently reconstructed closes; quantity, direction, timing, PnL arithmetic, and full-precision execution/trade timestamps matched. Scratch compile and installed assembly reload succeeded. Result ACKs: 2; reviewed-metadata ACKs: 2. The earlier four-session data-only audit has its own ACK and adds no performance observations.

## Interpretation and retained work

This setting missed the after-cost adoption gate in this finite sample. Across the original eight and new seven distinct evaluation sessions, there was only one qualifying day and one trade. That is insufficient to reject the entire NR7 family or establish robustness. Closed-trade drawdown is $245/$250; intratrade account-equity drawdown was not reconstructed. No profitable-day concentration statistic is informative with one losing trade.

Completed RSI October 7–9 tasks were removed from pending scheduling without deleting evidence. The Playback policy block is explicit and must not be retried or bypassed. CafeRange's positive sparse legacy records and unchanged risk cap are preserved with a broader coverage review task. Bollinger retains its cost/distinct-sample review; RSI awaits prospective data. OFI routine historical extension remains closed, and MACD is not scheduled for repetition.

Evidence: `research/nr7-history-extension-{manifest,coverage,results,ledgers,summary}.json`, `research/nr7-warmup-imports.json`, and `research/preserved-candidate-audit.json`.
