QVSD preliminary research — 2026-10-24
Open report.html for methodology, source analysis, limitations, and Windows export instructions.
No strategy is approved for live or competition deployment.
Public data: Yahoo chart endpoint, range=60d, interval=5m, NQ=F and GC=F.
Original responses are in data/. SHA256 and exclusions are in data_audit.json.
Run: python3 research/backtest.py
Tests: python3 -m unittest discover -s research -p 'test_*.py' -v
Render report after calculations: python3 research/build_report.py
Latest research uses proxy mini prices with micro contract multipliers, not actual micro executions.
Recent runs restart the account; recent_continuous_account tracks the non-reset path.
Windows NinjaTrader 6-month tick data and official contest hours/costs are still required.
