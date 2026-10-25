"""Count focused synthetic suites before running; preserve each attempt."""
import unittest
from datetime import datetime, timezone
from runner.core import ROOT, atomic, file_hash
from research.analyze_market_state import read, require


def main():
    plan = read('research/nq-goal-validation-readiness-plan.json')
    path = ROOT/'research/validation-packet-test-attempts.json'
    state = read(str(path.relative_to(ROOT))) if path.exists() else dict(attempts=[])
    require(len(state['attempts']) < plan['limits']['synthetic_suite_runs'], 'Suite budget exhausted')
    number = len(state['attempts'])+1
    record = dict(number=number, reserved_at_utc=datetime.now(timezone.utc).isoformat(), status='reserved')
    state['attempts'].append(record)
    atomic(path, state)
    suite = unittest.defaultTestLoader.loadTestsFromName('tests.test_validation_packet')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    evidence = dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skips=len(result.skipped), success=result.wasSuccessful(), suite_attempt=number,
        at_utc=datetime.now(timezone.utc).isoformat(),
        code_sha256=file_hash(ROOT/'research/validation_packet.py'),
        test_sha256=file_hash(ROOT/'tests/test_validation_packet.py'),
        scope='Synthetic metadata, failure gates, time/DST and no-submit invariants only; no strategy performance')
    record.update(status='passed' if result.wasSuccessful() else 'failed', **evidence)
    atomic(path, state)
    atomic(ROOT/'research/validation-packet-tests.json', evidence)
    if not result.wasSuccessful() or result.skipped:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
