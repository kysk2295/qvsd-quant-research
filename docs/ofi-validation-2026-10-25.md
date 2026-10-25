# NQ lagged best-quote OFI: finite native validation

Four preregistered NinjaTrader native backtests completed with four result ACKs and four reviewed-metadata ACKs. One fixed configuration, 12 previously observed sessions, 48 unique trades; cost variants repeat those trades and are not independent observations. No independent OOS claim.

| Exploratory segment | Trades | $5 roundtrip fee | $10 roundtrip fee |
|---|---:|---:|---:|
| Oct7–16, eight sessions |32|-$2,615|-$2,775|
| Oct19–22, four sessions |16|+$3,220|+$3,140|
| Combined |48|+$605|+$365|

Actual native fills were identical for requested two/four-tick slippage. Thus the nominal stress difference is fees only. A separate arithmetic adverse-cost scenario adding four ticks per fill reduces combined results to -$1,315/-$1,555; it does not simulate changed order execution. Late-segment net excluding its best day is -$590/-$650. Adoption is deferred for regime, concentration and execution-cost uncertainty, not a statistical rejection of every OFI strategy.

## Data and causality

The [original paper](https://arxiv.org/abs/1011.6402) studies contemporaneous price impact from best-quote events. This predictive NQ adaptation is a separate hypothesis. Real recorded NRD L1 Ask/Bid prices and replacement sizes were aggregated, not Last volume proxies. Header count/quantity checks passed for all12 source days. 4,590 of4,680 regular-session minutes met the frozen quality filter. Original file consistency cannot prove lossless exchange data.

At decision t, the strategy reads exactly the feature ending t-60seconds. Every contributing source timestamp precedes that feature end. The feature CSV SHA256 is pinned in strategy code and coverage evidence. All native signals matched the frozen CSV, threshold, side, timestamps, quantity, entry/exit chronology and native price-derived PnL. L1 order is preserved; there is no exchange sequence number. Shared ordering across L1/L2 is unavailable. L2 reconstruction was not validated or used.

Native primary bars are one minute; High Tick1 Last data supplies fills. TickReplay=false. No claim that Tick Replay replays historical bid/ask sizes, queue execution, or Playback validation. The blocked Playback/order-control path was not retried. No live connection or running strategy was present at assembly reload.

## Verification and next work

Thirteen Python tests and nine boundary assertions against the actual C# decision gate passed. Scratch and installed NinjaTrader compilation passed; existing CS8012 processor-target warning remains. Full native responses are retained locally; tracked `research/ofi-ledgers.json` contains matched signal/feature/trade evidence and response hashes. Results and manifests are under `research/ofi-*`.

Keep this rule fixed. Next evidence task is distinct future recorded quote coverage, followed by a separately preregistered finite validation. Do not optimize against these same12 sessions. RSI remains unchanged and deferred. Lifecycle is idle after this completed finite batch; no continuously running worker is claimed.
