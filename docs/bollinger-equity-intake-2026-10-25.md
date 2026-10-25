# Existing Bollinger equity audit and finite data intake

The original 52 trades, native results, frozen strategy rules, future plan, campaign registry and native budget remain unchanged. This turn publishes an already computed audit; it performs no new performance run or PnL recalculation.

| Round-trip fee | Net | Closed-trade DD | Last-mark holding-path DD bounds | Worst closed day |
|---|---:|---:|---:|---:|
| $5 | $1,455 | $2,215 | $3,067.50–$3,100 | -$990 |
| $10 | $1,195 | $2,260 | $3,110–$3,140 | -$1,010 |

These are conditional conservative bounds for fixed original simulated fills marked to observed Last prices, not exact executable liquidation or live-account drawdowns. Fees are split equally at entry and exit. Most fills have seconds-only timestamps; equal-time tick order is unresolved even for the four previously logged precise diagnostic trades. The upper bound need not be attainable. Missing exchange prints, bid/ask liquidation, queue, impact and changed execution paths are not reconstructed. Additional slippage sensitivity stays separate. The realized -$900 entry halt is not a hard loss cap: the worst day closes $110 beyond it at the $10 fee assumption.

Evidence: `research/bollinger-equity-path-audit.json` records source hashes, daily results and uncertainty. `research/equity-audit-immutable-inputs.json` protects original inputs. `research/equity-intake-tests.json` records 30 unit/synthetic checks and code hashes. Dashboard metadata adds this audit alongside unchanged original metrics and saves assessment history; ACK evidence is in `research/equity-intake-review-summary.json`.

## Data-only collector

Offline preflight: `python -m runner.future_data_collector`

Finite execution after a registered session closes: `python -m runner.future_data_collector --execute`

Use the workspace NT MCP virtualenv. The adapter imports the existing native Historical Data download function. It does not arm controls, reconnect Playback, query accounts, import ticks into NinjaTrader, or call a strategy/backtest. The Historical Data download button must already be readable and enabled; otherwise it stops with no control changes.

- Only the ten registered dates, October 26–November 6, qualify. ET16:00 is UTC20:00 before DST ends and UTC21:00 from November 2. The CLI uses actual UTC time, with no future-time override.
- At most three dates are handled per invocation. Native download is asynchronous: after one submission the invocation returns. A later explicit invocation verifies the file and quality before proceeding. No polling daemon or schedule exists.
- Each date consumes its one submission allowance in a durable locked ledger before the external request; total maximum ten. Exceptions and uncertain responses retain the allowance. No automatic download retries, overwrite or fallback download route.
- Existing files prevent duplicate download. Strict NRD integrity, stable source hash, ordered Last timestamps, valid NQ prices/sizes, all 390 RTH minutes, parquet and Last export hashes are checked before quality publication. Partial artifacts require inspection. Failed quality is not published as success; a missing dashboard ACK can be retried without redownloading.
- Data-quality telemetry has empty metrics/equity and explicitly records no performance evaluation. It cannot unlock the native campaign gate.

Dry-run and synthetic tests passed; adapter imports resolve. No future download was attempted, so real future-date end-to-end acquisition is not yet demonstrated. The older `future-data-intake-readiness.json` is the pre-adapter snapshot; the authoritative current capability report is `future-data-collector-readiness.json`.

The future performance decision remains November 7 at 10:00 KST, after all ten dates pass quality. No early outcome peeking. Native budget is still zero and the reserved future performance executor is not released. This research decision date does not establish competition readiness or a competition submission deadline. No background collection/research is running.
