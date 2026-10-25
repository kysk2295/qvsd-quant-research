# Windows NQ runner verification — 2026-10-25

## Delivered

Separate checkout `qvsd-experiment-runner`, branch `codex/windows-experiment-runner`.
SQLite durable queue, experiment fingerprint, single-process lock, one claimed
job, native write-ahead submission intent, recovery by known NT ID/instance,
timeout/cancellation, bounded preflight retry, pause/resume/stop, Python subprocess
adapter, native Backtest-only adapter and aggregate telemetry are implemented.
No live strategy or order endpoint is exposed by the runner.

Scheduled task `QVSD-NQ-Experiment-Runner` runs under the current interactive
user with limited privileges, at logon, no time limit, IgnoreNew, and up to three
one-minute failure restarts. Final observed daemon PID: **13816**, mode running,
phase idle. The queue is finite and empty of runnable cases, so the process sleeps
and continues heartbeats. It does not repeatedly optimize the same data.
Existing `QVSD-Dashboard-Reporter` remains running independently.

At 11:53 KST, **59/59 current snapshots were acknowledged by the production
server**, and the runner's distinct heartbeat was current. This is server ACK
evidence, not a claim of a new manual UI inspection in this Windows task.

## Execution accounting

| Category | Count | Interpretation |
|---|---:|---|
| Python calculations | 20 | NQ $20/point, Yahoo price proxy; 8 completed, 12 rejected |
| Actual native NT calculations | 4 | b1–b4 finished in NT; all 4 rejected by coverage validation |
| Superseded transport-preflight records | 29 | Preserved first manifest; no native submissions from this revision |
| Remaining native grid cases blocked | 5 | Same unreliable requested/loaded-window behavior |
| Multi-session order-flow study blocked | 1 | Insufficient audited multi-session L1/L2 |
| Total queue records | 59 | 8 completed, 16 rejected, 35 blocked; 0 queued/running/failed |

Completed means calculation finished, not strategy adoption. **Adopted strategies: 0.**

Initial localhost transport correction was tested before restarting the manifest.
All submitted NT jobs used SampleMACrossOver on NQ 12-26 and Backtest only. No
Playback seeking, connection changes, addon compilation, or live strategy activation
was performed. Original research checkout and dashboard reporter checkout were preserved.

## Native coverage investigation

b1–b3 requested 2026-09-28..09-29, but loaded 2026-09-30 07:05 through
2026-10-02 13:00 in NT-local timestamps. The bridge logged the requested settings,
used its A1 RunBacktest path, returned actual trade histories, and explicitly warned
that these numbers were not for the requested period. PnL remains diagnostic only.

The Playback clock is parked at 2026-10-02 00:00 US Eastern. Converted to Asia/Seoul
it is 2026-10-02 13:00, matching the loaded endpoint. Windows is Korea Standard Time;
NT Config.xml has an empty TimeZoneInfoSerializable override. The bridge's
Backtest_Window source compares US Eastern clock directly with NT-local To, and its
comment assumes equal zones. That warning logic is unsuitable on this machine.
This explains the clock comparison issue; it does not alone explain/fix the displaced
start date. The native loader is also anchoring its window to Playback.

One bounded follow-up, **b4 / nq-47dc92af04fc96383deb94e2**, explicitly requested
the observed 09-30 07:05..10-02 13:00 range. The engine instead loaded
**09-29 07:05..10-02 13:00**. Exact endpoint validation automatically rejected it.
Thus a valid requested-window NT reproduction was **not achieved**. Further
native comparisons on this data fingerprint are blocked. Do not reinterpret b4
as successful OOS, correct-period performance, or forward testing.

Next native work must repair/verify the loading path or use Strategy Analyzer
with independently checked dates/session/timezone, then reproduce one case before
resuming any parameter grid. The user's addon was not modified to force a success.

## Python research findings

The corrected NQ contract value is $20 per point, max eight contracts and $300
nominal entry risk. Larger stops often make size zero. All breakout configurations
in this fixed grid produced zero trades; no artificial minimum trade size was forced.

On the latest 15 complete sessions, base retest variants made $255 on two trades
and $545 on one trade; both had zero trades under the stressed assumptions. Failed-IB
made $1,875 base / $410 stress on five trades, but removing its three best trades
left -$465 / -$515. None had a day with four entries in that recent segment.
Positive totals are not adequate evidence for competition use. Cost scenarios
rerun sizing/entry eligibility; their trade sets can differ.

Earlier 35 sessions and later 15 sessions were already examined in prior research.
They are chronological diagnostics, not independent unused validation. This runner
does not yet implement an OFI/order-flow strategy, frozen-version walk-forward
selection, integrated competition account liquidation rules, or paper forward
execution on newly arriving data. These remain separate future stages.

## Tests and operations

- Before first actual run: runner 13/13, including ambiguity/recovery/timeout/lock/telemetry.
- After coverage guard: runner **16/16**.
- Existing backtest regression suite **8/8**; dashboard suite **6/6**.
- `git diff --check` passed.
- Queue deduplication, terminal history and server ACKs are retained locally.

From the runner checkout, using the existing Python environment:

```powershell
$py = 'C:\Users\User\Documents\Codex\2026-10-04\dlrj\work\nt8-mcp\.venv\Scripts\python.exe'
& $py -m runner status
& $py -m runner pause
& $py -m runner resume
& $py -m runner stop
```

Pause allows an existing calculation to finish; stop cancels the owned job on the
next worker tick. Both prevent new claims. Resume refuses uncertain submissions.
Raw job results, logs, database and manifests stay in ignored `data/runner/`.
Research design and literature sources: [runner README](../runner/README.md).
