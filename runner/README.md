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

Assumed base costs: 2 ticks slippage per execution, $5 round-trip per contract;
stress: 4 ticks and $10. These are assumptions, not verified broker fees. Native
NT applies its slippage model; commission is explicitly disabled in NT and
deducted from each returned trade by the adapter. Standard-bar fills do not
prove tick-by-tick executability. Native loaded bars/settings are retained.

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
