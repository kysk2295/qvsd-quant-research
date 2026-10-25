"""Count the preregistered synthetic-only suites before execution."""
import json
import unittest
from datetime import datetime, timezone

from runner.core import ROOT, ProcessLock, atomic, file_hash
from research.validation_packet import read_json, verify_protected

PLAN = 'research/nq-postrun-evaluator-preparation-plan.json'
PLAN_HASH = 'f9265b1e8cdaa047a3120409c89d738ad68c220b56dc33fe7427bff4dcdaaa95'
CODE = ['research/prospective_clock.py', 'research/prospective_cost_path.py',
        'research/prospective_postrun.py', 'tests/test_prospective_clock.py',
        'tests/test_prospective_cost_path.py', 'tests/test_prospective_postrun.py']


def main():
    with ProcessLock(ROOT/'data/runner/postrun-preparation-tests.lock'):
        if file_hash(ROOT/PLAN) != PLAN_HASH:
            raise ValueError('Plan changed')
        plan = read_json(ROOT/PLAN)
        verify_protected(ROOT, plan)
        path = ROOT/'research/postrun-preparation-test-attempts.json'
        state = read_json(path) if path.exists() else dict(attempts=[])
        number = len(state['attempts']) + 1
        if number > plan['limits']['synthetic_suite_runs']:
            raise RuntimeError('Synthetic suite budget exhausted')
        entry = dict(number=number, reserved_at_utc=datetime.now(timezone.utc).isoformat(), status='reserved')
        state['attempts'].append(entry)
        atomic(path, state)
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in
            ('tests.test_prospective_clock', 'tests.test_prospective_cost_path', 'tests.test_prospective_postrun'))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        okay = result.wasSuccessful() and not result.skipped
        evidence = dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
            skips=len(result.skipped), success=okay, suite_attempt=number,
            code_hashes={p: file_hash(ROOT/p) for p in CODE},
            failure_details=[dict(test=str(t), detail=d) for t, d in result.failures + result.errors],
            scope='Manufactured arrays/logs only; no real market outcomes, native calls or production attempts')
        entry.update(status='passed' if okay else 'failed', **evidence)
        atomic(path, state)
        atomic(ROOT/'research/postrun-preparation-tests.json', evidence)
        verify_protected(ROOT, plan)
        print(json.dumps(dict(suite_attempt=number, tests=result.testsRun, success=okay)))
        if not okay:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
