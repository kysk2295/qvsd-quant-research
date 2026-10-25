"""One centrally counted suite of synthetic execution integration checks."""
import json
import unittest
from datetime import datetime, timezone
from runner.core import ROOT, ProcessLock, atomic, file_hash
from research.validation_packet import read_json, verify_protected

PLAN = 'research/nq-production-executor-plan.json'
PLAN_HASH = '62dc98d16e6a5a309185a2920bd324469bec86fb6ddaffcc5ea97cb5dd0caddf'
CODE = ['runner/prospective_dataset.py', 'runner/prospective_executor.py', 'runner/campaign_gate.py',
        'tests/test_prospective_dataset.py', 'tests/test_prospective_executor.py',
        'tests/test_campaign_prospective_gate.py']
SUITES = ['tests.test_prospective_dataset', 'tests.test_prospective_executor',
          'tests.test_campaign_prospective_gate', 'tests.test_campaign_gate',
          'tests.test_prospective_attempt']


def main():
    with ProcessLock(ROOT/'data/runner/production-executor-tests.lock'):
        if file_hash(ROOT/PLAN) != PLAN_HASH:
            raise ValueError('Registered plan changed')
        plan = read_json(ROOT/PLAN)
        verify_protected(ROOT, plan)
        path = ROOT/'research/production-executor-test-attempts.json'
        attempts = read_json(path) if path.exists() else {'attempts': []}
        number = len(attempts['attempts'])+1
        if number > plan['limits']['synthetic_suite_runs']:
            raise RuntimeError('Synthetic suite budget exhausted')
        hashes = {p:file_hash(ROOT/p) for p in CODE}
        entry = dict(number=number, reserved_at_utc=datetime.now(timezone.utc).isoformat(),
                     status='reserved', code_hashes=hashes)
        attempts['attempts'].append(entry)
        atomic(path, attempts)
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in SUITES)
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        okay = result.wasSuccessful() and not result.skipped
        if hashes != {p:file_hash(ROOT/p) for p in CODE}:
            raise RuntimeError('Code changed during counted tests')
        evidence = dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
            skips=len(result.skipped), success=okay, suite_attempt=number, code_hashes=hashes, suites=SUITES,
            failure_details=[dict(test=str(t), detail=d) for t,d in result.failures+result.errors],
            native_calls=0, real_market_file_reads=0,
            scope='Synthetic ten-day import/Last/native-cache fixtures, fake HTTP and prior lifecycle/generic-gate regression checks')
        entry.update(status='passed' if okay else 'failed', **evidence)
        atomic(path, attempts)
        atomic(ROOT/'research/production-executor-tests.json', evidence)
        verify_protected(ROOT, plan)
        print(json.dumps(dict(attempt=number, tests=result.testsRun, success=okay)))
        if not okay:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
