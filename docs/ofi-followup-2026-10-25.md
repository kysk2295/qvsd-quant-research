# OFI historical extension and execution-cost diagnostic

Oct6 was the only remaining locally available, complete regular-session date not previously tested for OFI. Oct11/18 are Sundays; Oct23's known corrupt NRD remains excluded. No download or Playback access was attempted. Oct6 is earlier historical extension, not future forward validation or independent OOS.

Before outcomes, the audit budget and then a two-native-run extension were saved. All390 RTH minutes and header consistency passed;378 minutes met the unchanged quote-quality gate. The original strategy logic was copied unchanged into a distinct class with a different frozen feature path/hash. A pre-submission manifest validator rejected a missing nested role field; that metadata was corrected before any native test. No native retry occurred.

Two native tests generated the same four trades: +$700 with $5 roundtrip fees and +$680 with $10 fees. Signals matched frozen historical features, trade side, quantity, timestamps and price-derived PnL. Across13 observed sessions there are52 unique trades, not104: +$1,305/$1,045 after external fees. Separate additional4ticks-per-fill sensitivity reduces these totals to -$775/-$1,035. Adoption remains deferred.

## Distinguishing execution costs

- Requested native slippage2/4ticks produced identical actual fill tuples. It did not demonstrate different realized slippage; the reported net difference is external fees.
- Additional2/4ticks perfill are arithmetic adverse-cost scenarios. They do not change execution timing, stop placement or trading paths.
- The48 earlier unique trades were independently matched to strictly preceding recorded L1 quotes at serialized entry/exit timestamps and offsets100/1000ms. Positive sizes, uncrossed book and <=1second quote age were required. All observations were available. No native backtest was rerun.
- Touch repricing buys at ask and sells at bid, replacing native prices; full spread is not deducted again. Displayed one-contract liquidity does not guarantee a fill. Queue position, cancellations, routing delay and price impact remain unknown.

The zero-offset quote diagnostic had2 entry spreads and1 exit spread above4ticks, with maximum9ticks. The strategy's <=4tick spread filter belongs to the feature ending60seconds before the decision, not the current execution book. We did not alter the rule after seeing this.

Touch repricing at the serialized timestamps and+100/+1000ms yields diagnostic after-$5-fee totals of+$2,415/+$1,765/+$100 on the same48 trades. These are **not alternative backtest returns or execution-cost estimates**: native timestamps are serialized to whole seconds, so matching can precede the true execution by almost1second, and changing fill prices would change subsequent stops and exits. Keeping original exit times omits that path change. The diagnostic is not necessarily more conservative than native fills. Excluding its best day gives -$1,375/-$1,985/-$3,980. Raw quote evidence, ages and hashes are preserved in `research/ofi-touch-cost-audit.json`.

## Resume conditions

Keep threshold10,60second feature lag,5bar holding and original risk limits fixed. Resume a new finite native batch only after distinct full RTH quote sessions exist, original-file counts/size sums and timestamp order pass, and per-minute quality exclusions plus data role and budget are preregistered. Post-Oct25 dates may be prospective only if untouched by selection; earlier newly acquired dates remain historical extensions. No automated download or ongoing job has been scheduled.

Before claims about subsecond delay or executable PnL, obtain precise native execution timestamps and validate a causal order/stop path using permitted historical/offline tools. Existing policy-blocked Playback paths remain untouched. Preserve the RSI candidate unchanged. Two new result ACKs and six updated metadata ACKs were confirmed; lifecycle returned to idle after this finite batch.
