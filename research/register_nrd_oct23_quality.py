"""Register one bounded offline NRD quality diagnosis, preserving old evidence."""
from datetime import datetime, timezone
from pathlib import Path
from runner.core import ROOT, atomic, file_hash
from research.analyze_market_state import read, require

PLAN = 'research/nrd-oct23-quality-plan.json'
SERVER = Path(r'C:\Users\User\Documents\Codex\2026-10-04\dlrj\work\nt8-mcp\server')


def main():
    require(not (ROOT/PLAN).exists(), 'Existing diagnosis plan: inspect, do not duplicate')
    source = Path.home()/'Documents/NinjaTrader 8/db/replay/NQ 12-26/20261023.nrd'
    staged = ROOT/'data/runner/replay-stage/NQ 12-26/20261023.nrd'
    legacy = next(x for x in read('data/runner/replay-download-audit.json') if x['day'] == '20261023')
    require(source.stat().st_size == legacy['bytes'] and file_hash(source) == legacy['sha256'], 'Original differs from prior acquisition audit')
    require(file_hash(staged) == legacy['sha256'], 'Staging copy differs')
    protected = read('research/equity-audit-immutable-inputs.json')
    for path in ['research/nq-market-state-plan.json','research/nq-market-state-baseline.json',
                 'research/nq-market-state-publication.json','research/nq-state-response-plan.json',
                 'research/nq-state-response-results.json','research/nq-state-response-publication.json',
                 'research/stochastic-coverage.json','research/recent-tick-audit-20261025.json',
                 'research/state-response-data-readiness.json','data/runner/replay-download-audit.json',
                 'data/runner/replay-parquet-audit.json','docs/windows-replay-acquisition-2026-10-25.md']:
        protected[path] = file_hash(ROOT/path)
    require(all(file_hash(ROOT/p) == h for p,h in protected.items()), 'Protected evidence changed')
    source_hashes = {str(source):file_hash(source), str(staged):file_hash(staged)}
    representative = [Path.home()/f'Documents/NinjaTrader 8/db/replay/NQ 12-26/{d}.nrd' for d in ('20261002','20261022')]
    source_hashes.update({str(p):file_hash(p) for p in representative})
    decoder = SERVER/'nt8_mcp/nrd_offline.py'; tests = SERVER/'tests/test_nrd_offline.py'
    plan = dict(id='nq-nrd-oct23-quality-20261025', registered_at_utc=datetime.now(timezone.utc).isoformat(),
        scope='One offline diagnosis of2026-10-23 NRD/header price and volume disagreement; quality only, no price-response or strategy evaluation',
        source=str(source), source_sha256=legacy['sha256'], source_bytes=legacy['bytes'],
        source_hashes=source_hashes, immutable_hashes=protected,
        decoder=str(decoder), original_decoder_sha256=file_hash(decoder), original_decoder_tests_sha256=file_hash(tests),
        prior_evidence=['data/runner/replay-download-audit.json','docs/windows-replay-acquisition-2026-10-25.md','research/state-response-data-readiness.json'],
        limits=dict(baseline_full_decode=1, targeted_wire_inspection=1, concrete_parser_fix_attempts=1,
                    corrected_oct23_full_decode=1, representative_regression_full_decodes=2,
                    synthetic_test_suite_runs=2, downloads=0, native_calls=0, performance_tests=0, optimization=0),
        representative_dates_if_fixed=['2026-10-02','2026-10-22'],
        diagnostics=['Whole-file per-type header and decoded counts/volume/ranges/time span',
            'Full consumption, incomplete trailing record, unexpected type/encoding and timestamp order',
            'UTC/ET calendar coverage and RTH390minute coverage separately from whole-file integrity',
            'First range violation byte offset/record widths/flags, timestamp and record repetition evidence',
            'Distinguish evidence of parser defect, incomplete header/body synchronization, missing/duplicate records and unidentified corruption; do not overclaim'],
        quality_gate='Unchanged header checks plus exact per-type counts, time/order and positive tick-aligned Last records and390RTH minutes; no arbitrary correction, header fitting, deduplication or weakened tolerances',
        preservation='Read-only original NRD/staging and all old artifacts; new evidence under new names. Do not overwrite any existing parquet, text, audit or result. Do not modify unrelated dirty NT8 workspace files.',
        correction_policy='Only a concrete parser defect with independently encoded regression fixture permits one minimal fix. Otherwise preserve parser and keep date blocked. Record required source/native independent dump for reopening.',
        stop='One diagnosis or verified repair, tests/evidence saved to GitHub and data-quality dashboard ACK. No automatic rerun of market-state/hypothesis results and no future-period inspection.',
        status='registered')
    atomic(ROOT/PLAN, plan)
    ledger = read('research/campaign-data-analysis-ledger.json')
    require(not any(e['id'] == plan['id'] for e in ledger['entries']), 'Duplicate quality task')
    ledger['entries'].append(dict(id=plan['id'], kind='offline_data_quality', status='registered', plan=PLAN,
        plan_sha256=file_hash(ROOT/PLAN), limits=plan['limits'], attempts={}, native_runs=0, downloads=0))
    atomic(ROOT/'research/campaign-data-analysis-ledger.json', ledger)
    queue = read('research/evidence-work-queue.json')
    queue['tasks'].append(dict(id=plan['id'], kind='offline_data_quality', status='registered', plan=PLAN,
                               native_budget=0, downloads=0, stop=plan['stop']))
    atomic(ROOT/'research/evidence-work-queue.json', queue)
    backlog = read('research/candidate-backlog.json')
    backlog['oct23_data_quality'] = dict(id=plan['id'], status='registered', plan=PLAN,
                                       strategy_candidate=False, native_budget=0, downloads=0)
    atomic(ROOT/'research/candidate-backlog.json', backlog)
    print(dict(plan=PLAN, plan_sha256=file_hash(ROOT/PLAN), source_hash=legacy['sha256'], original_bytes=legacy['bytes']))


if __name__ == '__main__':
    main()
