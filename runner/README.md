# NQ finite experiment runner

This worker runs a predefined research queue, not live trading. It does not call
Codex, generate unlimited parameter combinations, download paid data, connect a
broker, enable a chart strategy, or change Playback. The cancelled 30-minute
Codex research automation is not restored.

## Research design

The initial manifest has exactly **29 cases**: 8 native SMA reference backtests
(two fixed SMA pairs × two chronological two-day windows × two assumed costs),
20 Python price-proxy cases (five strategy/parameter choices × two chronological
windows × two costs), and one explicitly blocked multi-session order-flow study.
Native SMA is a functional reference, not a recommended competition strategy.
The Python candidates are opening-range breakout, breakout retest, and failed
initial-balance breakout. No grid expands based on results.

### Literature basis and scope

- [Cont, Kukanov & Stoikov, The Price Impact of Order Book Events](https://arxiv.org/abs/1011.6402)
  documents a short-horizon relationship between best-quote order-flow imbalance
  and contemporaneous price changes in US stocks. This supports testing whether
  changes in supply/demand explain a breakout; it does not establish a profitable
  NQ forecast. OFI includes quote changes/cancellations and is not trade delta.
- [Gould & Bonart, Queue Imbalance as a One-Tick-Ahead Price Predictor](https://arxiv.org/abs/1512.03492)
  tests imbalance against the next mid-price movement in ten Nasdaq stocks.
  NQ execution costs, horizons and queues must be independently tested. Predicting
  a tick direction does not by itself imply an executable positive expectancy.
- [Bailey et al., The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)
  motivates preserving all trials and treating selected high backtest performance
  cautiously. Repeatedly choosing on the same recent window contaminates validation.
- [CME NQ specifications](https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.contractSpecs.html)
  specify $20 per index point and a 0.25-point tick ($5), distinct from MNQ.

The following are our proposed NQ hypotheses, not proven conclusions of those
papers: (1) volatility expansion plus price/flow confirmation continues an opening
range breakout; (2) a pullback followed by renewed aggressive flow resumes a trend;
(3) a range break with large aggression but weak price response subsequently fails.
First establish each price-only baseline, then add one flow feature and compare
its incremental effect with unchanged costs/risk/time rules. Keep no-trade cases,
measure turnover and tail losses, remove best trades as a concentration check,
and stress costs. L2 reconstruction, bid/ask classification and timestamp integrity
must pass before OFI/queue results can be interpreted. No current regime or winning
strategy is inferred from these papers alone.

Python uses Yahoo NQ prices with **$20/point**, max 8 contracts and a $300 nominal
entry-risk budget. Legacy code defaults remain unchanged for older callers;
the runner supplies the NQ multiplier in an isolated child. A zero-contract
decision is allowed. Gaps can exceed the nominal risk. The model does not
implement all competition account/drawdown rules. It is not execution proof.

The earlier period is 2026-08-14..10-02; the later period is 10-05..10-23.
These data have already been examined. The later period is a chronological
diagnostic, **not an untouched holdout**. All predefined configurations are
reported; a positive result does not automatically qualify a strategy. Net
nonpositive Python cases are marked rejected. Native smoke cases remain
completed regardless of PnL because completion only verifies computation.
Next research needs longer verified NQ L1/L2, frozen hypotheses, a new untouched
time window, and walk-forward selection strictly within training windows.

Evaluation stages remain distinct: recent-period training/optimization, unused
chronological validation, historical regime risk review, and paper forward
testing on genuinely new incoming data. A 20-session train / 5-session test
window is only an example, not a default forced onto inadequate data. Historical
Playback is replay validation, never new-data forward testing. Once OOS results
inform a modification, that window becomes examined data for the new version.
Every attempt remains in the queue history, including preflight failures.

Assumed base costs: 2 ticks slippage per execution, $5 round-trip per contract;
stress: 4 ticks and $10. These are assumptions, not verified broker fees. Native
NT applies its slippage model; commission is explicitly disabled in NT and
deducted from each returned trade by the adapter. Standard-bar fills do not
prove tick-by-tick executability. Native loaded bars/settings are retained.
Cost scenarios rerun sizing and entry eligibility, so the trade sets can differ;
this is not a fixed-ledger fee sensitivity calculation.

Native results now fail closed when requested and loaded periods do not match.
A mismatch blocks remaining native comparisons on the same data fingerprint.
An explicitly declared `expected_bars` window permits one functional reproduction
of an observed partial Playback range, checked for exact first/last bar equality.
It does not authorize arbitrary-date backtests or establish full-session coverage.
The bridge compares the US Eastern Playback clock with NT-local timestamps without
conversion; its warning remains in evidence even when an explicit observed local
window matches. This runner does not patch or reload the user's bridge.

## Persistence and controls

Run from the repository root with the existing Python environment:

```powershell
$py = 'C:\Users\User\Documents\Codex\2026-10-04\dlrj\work\nt8-mcp\.venv\Scripts\python.exe'
& $py -m runner manifest
& $py -m runner enqueue
& $py -m runner resume
& $py -m runner run
& $py -m runner status
& $py -m runner pause
& $py -m runner resume
& $py -m runner stop
```

`pause` stops new claims and lets an active calculation finish. `stop` prevents
new claims and asks the worker to cancel its own active job. The daemon remains
idle so controls are durable across logon. `resume` refuses uncertain native
submissions. There is no unsafe one-command reset of this latch: inspect native
jobs and queue evidence before an explicit manual resolution.

SQLite WAL, FULL sync, a unique fingerprint and a Windows byte lock enforce
one local runner and one claimed experiment. Fingerprints include engine,
strategy, data hash, code commit/hash, date/month window, parameters and costs.
Code and files are checked again before execution. Native submission intent is
persisted before HTTP POST; a lost response blocks and pauses rather than
resubmitting. Known IDs are polled after recovery, with NT instance validation.
Timeout cancels only the known owned job. Unconfirmed cancellation pauses the
queue. External clients must not launch simultaneous jobs; preflight detects
existing active jobs but cannot atomically lock other NT clients.

Preflight failure retries once after five minutes, then blocks. Native timeout
is three minutes. Idle sleep is 15 seconds. Python work has a subprocess timeout;
after an unconfirmed crash it blocks rather than spawning another copy.
No automatic retry of terminal jobs; enqueueing the identical manifest dedupes.

`data/runner/` is ignored: database, raw native results, manifest with local
paths, subprocess logs and telemetry snapshots stay local. Only aggregate
metrics, settings, evidence and hashes are uploaded. Credentials are read from
the preexisting protected dashboard worker config and never logged.

The runner has its own heartbeat ID `windows-experiment-runner` and snapshot
sender; the existing `windows-research` reporter remains separate. A healthy
reporter does not imply a healthy runner. Heartbeats and up to four changed
snapshots are sent each cycle; acknowledgments persist only after server success.
Progress is stage-based, not a fabricated percent of elapsed computation.
The Windows logon task is `QVSD-NQ-Experiment-Runner`, current user / limited,
no execution time limit, one instance, bounded failure restarts. Windows must
remain awake and logged in for NinjaTrader. An empty finite queue idles; it does
not invent new research or repeatedly mine the same data all day.

## Verification

Before actual native submission run `python -m unittest runner.test_runner -v`.
Tests cover restart without resubmission, ambiguous POST, timeout cancellation,
unconfirmed cancellation, deduplication, exclusive claim/lock, bounded preflight
retry, pause/stop, data changes, cost reconstruction and dashboard schema.
