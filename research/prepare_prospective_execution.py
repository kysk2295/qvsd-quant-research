"""One metadata assessment of phase-correct execution readiness. No transport."""
import json
from datetime import datetime, timezone
from runner.core import ROOT, atomic, file_hash
from research.validation_packet import (read_json, verify_protected, write_exclusive_json,
    load_metadata, inspect_evidence, READINESS_PLAN)
from research.prospective_execution_contract import phase_readiness

PLAN = 'research/nq-prospective-execution-preparation-plan.json'
PLAN_HASH = 'cea24f4bd3bd46c092a9e712811ccea492bad2e59f73a6984101d025caaeb172'
RESULT = 'research/prospective-execution-readiness.json'
EXECUTION = 'research/prospective-execution-preparation-attempt.json'


def main():
    if file_hash(ROOT/PLAN) != PLAN_HASH:
        raise ValueError('Preparation plan changed')
    plan = read_json(ROOT/PLAN)
    verify_protected(ROOT, plan)
    if (ROOT/RESULT).exists():
        raise FileExistsError('Assessment already saved')
    now = datetime.now(timezone.utc)
    record = dict(id=plan['id'], plan_sha256=PLAN_HASH, metadata_assessments=1,
        reserved_at_utc=now.isoformat(), status='reserved', native_calls=0,
        production_attempt_reservations=0)
    write_exclusive_json(ROOT/EXECUTION, record)
    try:
        old_plan = read_json(ROOT/READINESS_PLAN)
        draft = inspect_evidence(load_metadata(ROOT, old_plan, now=now), now)
        result = phase_readiness(draft)
        result.update(id=plan['id'], assessed_at_utc=now.isoformat(), plan_sha256=PLAN_HASH,
            input_role='fresh JSON metadata only; existing performance fields unused; future session files skipped',
            available_evidence=draft['available_evidence'], dates=draft['dates'],
            native_calls=0, downloads=0, performance_calculations=0, production_attempt_reservations=0,
            code_hashes={p:file_hash(ROOT/p) for p in ('runner/prospective_attempt.py',
                'research/prospective_execution_contract.py','research/prepare_prospective_execution.py')},
            production_bridge_and_campaign_gate_unchanged=True,
            remaining_postrun_work=['Generalize fullprecision clock and cumulative CLOCK_TRADE snapshots',
                'Raw Last/BAR/signal and trade ledger reconciliation for fixed ten dates',
                'Marked Last path and frozen cost/best-positive-day assessments'])
        verify_protected(ROOT, plan)
        write_exclusive_json(ROOT/RESULT, result)
        record.update(status='completed', result=RESULT, result_sha256=file_hash(ROOT/RESULT))
        atomic(ROOT/EXECUTION, record)
        print(json.dumps(dict(result=RESULT, pre_run_unmet=len(result['pre_run_unmet']),
            post_run_required=len(result['post_run_required']), native_calls=0)))
    except Exception as exc:
        record.update(status='failed_no_retry', error=type(exc).__name__+': '+str(exc))
        atomic(ROOT/EXECUTION, record)
        raise


if __name__ == '__main__':
    main()
