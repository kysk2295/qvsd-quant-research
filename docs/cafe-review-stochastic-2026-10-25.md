# CafeRange review and stochastic pilot

## CafeRange: preserve evidence, defer adoption

Reviewed the 12 positive legacy records from three configurations across cost and fill variants. These are not 12 independent profitable candidates. Original lifecycle status, metrics, and prior assessments remain preserved; only the current research assessment was updated.

Representative development/base-cost records:

| Configuration | Trades | Net | Remove best profitable trade | Extra 4 ticks per fill | Observed risk > $300 exclusions |
|---|---:|---:|---:|---:|---:|
| OR retest 15 minutes | 1 | $360 | $0 | $320 | 7 |
| OR retest 30 minutes | 2 | $95 | -$265 | $15 | 13 |
| Failed IB 60 minutes | 4 | $1,455 | -$565 | $1,295 | 26 |

Per-record daily PnL including zero-trade dates, gross-profit concentration, removal of the best trade/day, and additional 2/4-tick sensitivity are in `research/cafe-sparse-review.json`. Risk exclusions count only observed `SIZE_REJECT` records whose estimated risk exceeds $300; full legacy filter counts and counterfactual profits of rejected signals remain unknown. The risk estimate is `(stop distance + 2 points) * $20 + $10`; it is not a guaranteed realized loss cap. The cap was not raised.

The session inventory compares full-RTH range and absolute open-to-close movement divided by range. The 15-minute retest and failed-IB configurations have 15 observed sessions and six available untried dates; the 30-minute retest has 11 observed sessions and ten untried dates. All untried daily ranges lie inside the observed range span. These nearby September/October dates do not establish independent broad-regime coverage.

Existing hashed 200-bar ETH coverage evidence is reusable for October 7–9, and for October 19–22 where untried for the 30-minute setting. September 23–25 ETH warmup remains unverified. No CafeRange native reruns were made. Full-session descriptive metrics must not become retrospective intraday entry filters.

NR7 retains its negative one-trade observed result and an explicit insufficient-sample disposition. Additional testing requires a separately registered distinct-regime question and actual setup exposure; no same-window reruns or lookback tuning.

## New candidate: published fast stochastic crossover

Repository cafe summaries were reviewed first. The original article 11 and 32 pages were unavailable through the current web fetch; their code was not claimed verified. A new candidate was taken from [AlgoTest's own published demonstration code](https://docs.algotest.in/signals/pinescripts/stochastic_oscillator_strategy/): raw stochastic K14, D=SMA3(K), crossover with K below20 for long and crossunder above80 for short. This is fast stochastic, not slow14/3/3 or StochRSI.

The NQ adaptation was registered before testing: one-minute RTH reset; entries09:50–15:25 ET, one contract, flat only, maximum4/day, 48-tick stop, 96-tick target, 20-bar/15:55 exit, and a -$900 realized-after-$10/trade entry gate. The original code's50/100-point exits were not copied as NQ risk assumptions. One fixed configuration; maximum two native attempts; no optimization.

| Native setting | Unique trade observations | After fee | Closed-trade drawdown | Extra 4 ticks per fill |
|---|---:|---:|---:|---:|
| 2 ticks; $5 round-trip fee | 60 | -$285 | $3,255 | -$2,685 |
| 4 ticks; $10 round-trip fee | Same 60 | -$585 | $3,380 | -$2,985 |

All 15 evaluated dates had four trades. Exits:20 profit targets,40 stops; the time-exit branch was not exercised. The actual native fill tuples are identical, so the nominal setting difference changes assumed fees only. Extra friction is separate arithmetic sensitivity. Removing the best day gives -$1,475/-$1,755. This finite configuration misses the adoption gate; this is not a rejection of all stochastic strategies.

Verification:11 boundary checks against actual C# math; scratch compilation and installed assembly reload; 5,850 independently aggregated raw-Last OHLC bars and indicator/crossover comparisons per run; signal, quantity, direction, PnL, non-overlap, daily limits, and full-precision simulated clock matching. Historical Last fills do not establish live queue behavior or account-equity drawdown compliance. Dates were previously observed, not independent OOS.

Dashboard:12 CafeRange ledger-review ACKs,24 regime-metadata ACKs including reuse of existing ETH evidence,2 NR7 sample-status ACKs; stochastic2 result ACKs and2 reviewed-result ACKs. No purchases, live trading, policy-blocked Playback retries, or recurring jobs were used. OFI routine extension remains closed.

Artifacts: `research/cafe-sparse-review.json`, `research/cafe-regime-inventory.json`, `research/stochastic-{source-review,manifest,coverage,results,ledgers,summary}.json`.
