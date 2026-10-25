import unittest
from datetime import datetime,timezone
from runner.core import ROOT,atomic,file_hash
from research.analyze_market_state import read,require


def main():
    ledger=read('research/campaign-data-analysis-ledger.json')
    entry=next(e for e in ledger['entries'] if e['id']=='nq-nrd-oct23-quality-20261025')
    attempts=entry['attempts'].setdefault('synthetic_test_suite_runs',dict(count=0))
    require(attempts['count']<2,'Synthetic suite budget exhausted')
    attempts['count']+=1; atomic(ROOT/'research/campaign-data-analysis-ledger.json',ledger)
    suite=unittest.defaultTestLoader.loadTestsFromName('tests.test_nrd_quality_trace')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    atomic(ROOT/'research/nrd-oct23-tests.json',dict(tests_run=result.testsRun,failures=len(result.failures),
        errors=len(result.errors),skips=len(result.skipped),success=result.wasSuccessful(),
        at_utc=datetime.now(timezone.utc).isoformat(),suite_attempt=attempts['count'],
        trace_sha256=file_hash(ROOT/'research/nrd_trace.py'),test_sha256=file_hash(ROOT/'tests/test_nrd_quality_trace.py'),
        scope='Existing decoder synthetic tests plus observation-hook parity and timezone summary boundary tests; no real-date acceptance inference'))
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
