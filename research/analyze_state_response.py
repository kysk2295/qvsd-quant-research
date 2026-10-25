"""One fixed predictive-association study of previously observed NQ sessions."""
from datetime import datetime, timezone
from runner.core import ROOT, atomic, file_hash
from research.analyze_market_state import read, require
from research.market_state_metrics import validate_minutes
from research.state_response_metrics import window_state, extract_event, event_summary, day_summary

PLAN = 'research/nq-state-response-plan.json'
PLAN_HASH = 'f4b97125dcac27f083c820d49eefb9b06f5ffffd35974346856fa09b21cb2de4'
RESULT = 'research/nq-state-response-results.json'


def verify(plan):
    require(file_hash(ROOT/PLAN) == PLAN_HASH, 'Registered study changed')
    for p, h in {**plan['original_input_hashes'], **plan['immutable_hashes']}.items():
        require(file_hash(ROOT/p) == h, 'Preserved input changed: '+p)


def positive(value):
    return value is not None and value > 0


def main():
    require(not (ROOT/RESULT).exists(), 'Study already calculated; no repeated run')
    plan = read(PLAN); verify(plan)
    ledger_path = ROOT/'research/campaign-data-analysis-ledger.json'
    ledger = read('research/campaign-data-analysis-ledger.json')
    entry = next(e for e in ledger['entries'] if e['id'] == plan['id'])
    require(entry['status'] == 'registered' and entry['plan_sha256'] == PLAN_HASH, 'Unregistered or repeated study')
    cache = read('research/stochastic-coverage.json')
    require(cache['complete'] and cache['timezone'] == plan['timezone'], 'Cache metadata mismatch')
    require(sorted(cache['sessions']) == plan['dates'] and cache['sources'] == plan['sources'], 'Coverage/source mismatch')
    for source in plan['sources']:
        require(file_hash(source['path']) == source['sha256'], 'Last source hash mismatch')
    for date in plan['dates']:
        validate_minutes(cache['sessions'][date], 570, 960)
    entry.update(status='running', calculation_reserved_at_utc=datetime.now(timezone.utc).isoformat())
    atomic(ledger_path, ledger)
    states = {}
    events = []
    for index, date in enumerate(plan['dates']):
        session = cache['sessions'][date]
        for clock in plan['clocks_minutes']:
            # References below use only earlier dates. These values may serve later dates.
            past = window_state([session[str(m)] for m in range(clock-30, clock)])
            future = window_state([session[str(m)] for m in range(clock+1, clock+31)])
            if index >= 5:
                reference_dates = plan['dates'][index-5:index]
                references = [states[(d,clock)] for d in reference_dates]
                snapshot, label = extract_event(session, clock, references, date)
                events.append(dict(date=date, clock=clock, clock_et=f'{clock//60:02d}:{clock%60:02d}',
                    group='recent' if date in plan['recent_dates'] else 'earlier',
                    feature_available_et=f'{date}T{clock//60:02d}:{clock%60:02d}:00',
                    response_start_minute=clock+1, response_end_exclusive_minute=clock+31,
                    snapshot_reconstructed_historically=True, **snapshot, **label))
            states[(date,clock)] = dict(date=date, clock=clock, past_rms=past['rms'], future_rms=future['rms'])
    require(len(events) == 60, 'Expected60 fixed observations')
    daily = [dict(date=date, **event_summary([r for r in events if r['date'] == date])) for date in plan['study_dates']]
    groups = dict(all=day_summary(daily),
        earlier=day_summary([d for d in daily if d['date'] in plan['earlier_dates']]),
        recent=day_summary([d for d in daily if d['date'] in plan['recent_dates']]))
    leave_one = [dict(omitted_day=d['date'], **day_summary([v for v in daily if v['date'] != d['date']])) for d in daily]
    conditions = {}
    for hypothesis in ('h1','h2'):
        key = hypothesis+'_daily_rho'
        conditions[hypothesis] = dict(
            all_daily_correlations_defined=groups['all'][key]['count'] == 10,
            all_median_positive=positive(groups['all'][key]['median']),
            earlier_median_positive=positive(groups['earlier'][key]['median']),
            recent_median_positive=positive(groups['recent'][key]['median']),
            all_leave_one_day_out_medians_positive=all(positive(v[key]['median']) for v in leave_one))
    conditions['h2'].update(all_forecast_pairs_defined=groups['all']['forecast_pairs'] == 60,
        all_mean_mae_improvement_positive=positive(groups['all']['mean_mae_improvement']),
        earlier_mean_mae_improvement_positive=positive(groups['earlier']['mean_mae_improvement']),
        recent_mean_mae_improvement_positive=positive(groups['recent']['mean_mae_improvement']),
        all_leave_one_day_out_mean_improvements_positive=all(positive(v['mean_mae_improvement']) for v in leave_one))
    assessments = {k:dict(conditions=v, consistency_gate_passed=all(v.values()),
        conclusion='descriptive_consistency_only_requires_independent_validation' if all(v.values()) else 'mixed_or_unsupported_in_development_sample')
        for k,v in conditions.items()}
    result = dict(id=plan['id'], kind=plan['kind'], created_at_utc=datetime.now(timezone.utc).isoformat(),
        plan=PLAN, plan_sha256=PLAN_HASH, dates=plan['dates'], study_dates=plan['study_dates'],
        earlier_dates=plan['earlier_dates'], recent_dates=plan['recent_dates'],
        events=events, daily=daily, groups=groups, pooled_diagnostic=event_summary(events),
        by_clock_diagnostic=[dict(clock=clock, **event_summary([r for r in events if r['clock'] == clock])) for clock in plan['clocks_minutes']],
        leave_one_day_out=leave_one, assessments=assessments,
        quality=dict(passed=True, sessions=15, minute_bars=5850, evaluation_days=10, events=60,
            clocks_per_day=6, feature_lookback_minutes=30, gap_minutes=1, response_minutes=30,
            source_hashes_verified=True, references_strictly_prior_five_dates=True,
            nonoverlapping_response_windows_within_day=True, frozen_inputs_unchanged=True),
        original_input_hashes=plan['original_input_hashes'], immutable_hashes=plan['immutable_hashes'],
        code_hashes={p:file_hash(ROOT/p) for p in ['research/analyze_state_response.py','research/state_response_metrics.py','tests/test_state_response.py']},
        native_runs=0, strategy_performance_runs=0, downloads=0, parameter_search=0,
        independent_oos=False, strategy_adopted=False, causal_identification=False,
        limits=[
            'Previously consumed development data; two predictive hypotheses, not pure quality checks. All results logged; no new untouched sample.',
            'Only10 evaluation days, six dependent observations/day. Daily rank correlation is coarse; no significance or population inference.',
            'One-minute excluded gap is a measurement convention, not proof of practical latency or executable fills.',
            'Signed directional efficiency association is not the same as high absolute efficiency improving trade win rate.',
            'H2 is a movement-scale forecast with fixed multiplier1; lower error would not establish profitable direction or safe position sizing.',
            'One-minute RMS includes drift and omits full intraminute paths. No quotes, spread, aggressor inference, stop/target or execution model.',
            'Clock decomposition and leave-one-day-out values are diagnostics only; do not select favorable hours, omit unfavorable dates or flip signs after seeing results.',
            'Existing Bollinger future reservation and campaign native budget remain untouched. No scheduling or repeated tests.'])
    verify(plan)
    atomic(ROOT/RESULT, result)
    entry.update(status='analyzed', outcomes_inspected=True, result=RESULT, result_sha256=file_hash(ROOT/RESULT))
    atomic(ledger_path, ledger)
    print(dict(result=RESULT, events=60, evaluation_days=10, assessments=assessments, native_runs=0))


if __name__ == '__main__':
    main()
