# Quant Lab

Railway hosts the private telemetry dashboard. Windows runs experiments and reports outbound over HTTPS. The server has no trade execution, command execution, or experiment scheduling endpoint.

## Dashboard

- Authenticated UI, 3-second refresh; worker heartbeat every 15 seconds and offline after 45 seconds.
- Filter/search/sort runs, inspect equity curves and parameters, export the filtered result table as CSV.
- Experiment states: queued, running, completed, failed, rejected, blocked. Completed means computation finished, not accepted for trading.
- SQLite in Railway volume `/data/research.sqlite3` persists through restarts. Deploy one replica. Run/event retention: latest 2,000 runs returned, latest 1,000 state-transition events retained.
- Seeded 12 cases are historical Yahoo proxy results, explicitly archived. No synthetic live counters.
- `DASHBOARD_PASSWORD` authenticates the browser. `INGEST_TOKEN` is an admin ingest key, never a browser credential. `PAIRING_CODE` is a one-use worker pairing secret; rotate its environment value to pair another worker. Worker credentials remain valid until their hash is removed from the credentials table.

## Windows setup

Requires Python 3.10+ and the repository checkout. No additional dependency is needed for the reporter. If Windows lacks IANA time zones, install `tzdata` to run the existing backtest.

```powershell
python dashboard/reporter.py --url https://YOUR-DOMAIN --pair-code YOUR-ONE-TIME-CODE --once
python dashboard/reporter.py
```

The first command saves `.dashboard-worker.json` locally; never commit/share it. The long-running reporter watches `data/telemetry/*.json` and retries failed uploads. `.dashboard-state.json` is its durable per-file upload checkpoint. Start only one reporter per checkout. Use Task Scheduler at user logon to keep it running. The computer must remain awake and online; the dashboard marks a disconnected worker offline.

Experiment code reports state using `emit` (each new experiment/rerun needs a unique ID):

```python
from dashboard.reporter import emit
run = dict(id='unique-run-id', strategy='my-strategy', symbol='NQ',
           source='Native Replay / exploratory', worker='windows-research',
           dataset='contract + dates + bar type', status='running', progress=10,
           phase='Loading data', params={})
emit(run)
# ... perform actual computation ...
run.update(status='completed', progress=100, phase='Computed; not approved',
           metrics={'net': 100.0, 'trades': 25}, completed_at=__import__('time').time())
emit(run)
```

Include data hash, code commit, costs, failure/rejection reason, and an equity array of `{date, value}` when available. Do not include credentials, account identifiers, or raw market records. Keep each snapshot under 1 MB and curves under 3,000 points. Progress is reported by the experiment itself, never inferred from elapsed time. If a process crashes, the last running snapshot remains visible; inspect experiment logs and publish a failed status. Heartbeat confirms reporter connectivity, not experiment-process health.

`python dashboard/run_baseline.py` runs a **finite** 12-case reproduction using the existing Yahoo data. It does not optimize, validate native data, or launch an endless experiment loop. Use it once to verify end-to-end reporting. Research code can then emit results for new strategies without changing the dashboard.

## Verification

```sh
python3 -m unittest discover -s dashboard/tests -v
```

Local UI: set `DASHBOARD_PASSWORD`, `INGEST_TOKEN`, and `COOKIE_SECURE=0`, then `python3 dashboard/server.py` (development only). Production uses Gunicorn via Dockerfile with secure cookies. Set `PUBLIC_ORIGIN` to the exact HTTPS dashboard origin for proxy-safe form validation.

## Deployment

Railway project: `qvsd-research-lab`; service: `dashboard`; volume: `/data`.
Infrastructure is defined in `.railway/railway.ts` (Railway SDK is a dev dependency). Use `npm ci`, then `railway config plan` and inspect before `railway config apply`. The volume and its mount must be preserved. Deploy application code with `railway up --service dashboard`. Secrets are Railway variables; local `.dashboard-secrets.json` is ignored. Public source contains no credentials or proprietary ticks.
