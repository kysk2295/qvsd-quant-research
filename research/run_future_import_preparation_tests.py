"""Centrally counted synthetic import preparation checks. No live endpoint."""
import json
import unittest
from datetime import datetime, timezone
from runner.core import ROOT, ProcessLock, atomic, file_hash
from research.validation_packet import read_json, verify_protected

PLAN = 'research/nq-future-import-preparation-plan.json'
PLAN_HASH = 'db05c62061142ac43748251dfaf0b34e5432152a071643316cd55dee46d22209'
CODE = ['runner/future_import_packet.py', 'runner/future_data_importer.py',
        'tests/test_future_import_packet.py', 'tests/test_future_data_importer.py']


def main():
    with ProcessLock(ROOT/'data/runner/future-import-preparation-tests.lock'):
        if file_hash(ROOT/PLAN) != PLAN_HASH:
            raise ValueError('Registered plan changed')
        plan = read_json(ROOT/PLAN)
        verify_protected(ROOT, plan)
        path = ROOT/'research/future-import-preparation-test-attempts.json'
        state = read_json(path) if path.exists() else {'attempts': []}
        number = len(state['attempts'])+1
        if number > plan['limits']['synthetic_suite_runs']:
            raise RuntimeError('Synthetic suite budget exhausted')
        hashes = {p: file_hash(ROOT/p) for p in CODE}
        entry = dict(number=number, reserved_at_utc=datetime.now(timezone.utc).isoformat(),
                     status='reserved', code_hashes=hashes)
        state['attempts'].append(entry)
        atomic(path, state)
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in
                    ('tests.test_future_import_packet', 'tests.test_future_data_importer'))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        okay = result.wasSuccessful() and not result.skipped
        if hashes != {p: file_hash(ROOT/p) for p in CODE}:
            raise RuntimeError('Code changed during tests')
        evidence = dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
            skips=len(result.skipped), success=okay, suite_attempt=number, code_hashes=hashes,
            failure_details=[dict(test=str(t), detail=d) for t, d in result.failures+result.errors],
            native_calls=0, real_market_data_reads=0,
            scope='Temporary synthetic Last/quality/ACK fixtures and fake transport only; native transport is mocked')
        entry.update(status='passed' if okay else 'failed', **evidence)
        atomic(path, state)
        atomic(ROOT/'research/future-import-preparation-tests.json', evidence)
        verify_protected(ROOT, plan)
        print(json.dumps(dict(suite_attempt=number, tests=result.testsRun, success=okay)))
        if not okay:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
