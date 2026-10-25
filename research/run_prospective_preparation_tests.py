"""Bounded synthetic lifecycle and result-contract test suites."""
import unittest
from datetime import datetime, timezone
from runner.core import ROOT, atomic, file_hash
from research.validation_packet import read_json, verify_protected
from research.prepare_prospective_execution import PLAN, PLAN_HASH


def main():
    if file_hash(ROOT/PLAN) != PLAN_HASH:
        raise ValueError('Plan changed')
    plan = read_json(ROOT/PLAN)
    verify_protected(ROOT, plan)
    path = ROOT/'research/prospective-preparation-test-attempts.json'
    state = read_json(path) if path.exists() else dict(attempts=[])
    number = len(state['attempts'])+1
    if number > plan['limits']['synthetic_suite_runs']:
        raise RuntimeError('Synthetic suite budget exhausted')
    entry = dict(number=number, reserved_at_utc=datetime.now(timezone.utc).isoformat(), status='reserved')
    state['attempts'].append(entry)
    atomic(path, state)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in
        ('tests.test_prospective_attempt', 'tests.test_prospective_execution_contract'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    okay = result.wasSuccessful() and not result.skipped
    evidence = dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skips=len(result.skipped), success=okay, suite_attempt=number,
        code_hashes={p:file_hash(ROOT/p) for p in ('runner/prospective_attempt.py',
            'research/prospective_execution_contract.py','tests/test_prospective_attempt.py',
            'tests/test_prospective_execution_contract.py')},
        scope='Temporary fixtures and fake transport only; no real engine/job/file outcomes or production reservation')
    entry.update(status='passed' if okay else 'failed', **evidence)
    atomic(path, state)
    atomic(ROOT/'research/prospective-preparation-tests.json', evidence)
    verify_protected(ROOT, plan)
    if not okay:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
