"""Persist reproducible test evidence; no network or trading calls."""
import unittest
from datetime import datetime,timezone
from runner.core import ROOT,atomic,file_hash

def main():
    modules=['tests.test_last_equity_bounds','tests.test_future_data_intake','tests.test_future_data_collector','tests.test_campaign_gate']
    suite=unittest.defaultTestLoader.loadTestsFromNames(modules)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    files=[p.replace('.','/')+'.py' for p in modules]+['research/last_equity_bounds.py','runner/future_data_intake.py','runner/future_data_collector.py','runner/campaign_gate.py']
    report=dict(tests_run=result.testsRun,passed=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors),
        modules=modules,source_hashes={p:file_hash(ROOT/p) for p in files},checked_at_utc=datetime.now(timezone.utc).isoformat(),
        external_calls=0,scope='Synthetic/unit tests; existing equity audit not recalculated; no live download claim.')
    atomic(ROOT/'research/equity-intake-tests.json',report)
    if not result.wasSuccessful():raise SystemExit(1)

if __name__=='__main__':main()
