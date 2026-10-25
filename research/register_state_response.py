"""Register a finite, outcome-bearing development study before its calculations."""
from datetime import datetime, timezone
from runner.core import ROOT, atomic, file_hash
from research.analyze_market_state import read, require, verify_hashes

PLAN = 'research/nq-state-response-plan.json'


def main():
    require(not (ROOT/PLAN).exists(), 'Study already registered')
    previous = read('research/nq-market-state-plan.json')
    verify_hashes(previous)
    dates = previous['dates']
    inputs = {p: file_hash(ROOT/p) for p in (
        'research/stochastic-coverage.json', 'research/nq-market-state-plan.json',
        'research/nq-market-state-baseline.json', 'research/market_state_metrics.py')}
    plan = dict(id='nq-state-response-20261025', registered_at_utc=datetime.now(timezone.utc).isoformat(),
        label='NQ 사전 상태와 후속 가격 반응 연구',
        authorization='User requested continuation of market-state-based research after baseline report',
        kind='Outcome-bearing predictive-association development study; NOT data-quality-only or independent OOS',
        instrument='NQ DEC26', timezone='America/New_York', dates=dates,
        warmup_dates=dates[:5], study_dates=dates[5:], earlier_dates=dates[5:10], recent_dates=dates[10:],
        clocks_minutes=[600, 660, 720, 780, 840, 900],
        window=dict(lookback=30, gap=1, horizon=30,
            feature='Minute keys[t-30,t); known only at/after t',
            response='Minute keys[t+1,t+31); first open to last close; fully known at t+31',
            gap_policy='Entire decision minute[t,t+1) excluded from feature and response; not a latency guarantee'),
        reference_sessions=5,
        reference='Strictly prior5 dates, same clock and same feature/response window. Never current day or full-sample normalization.',
        design_reason='Fixed hourly grid covers the session without selecting the previously highlighted10:00-10:30 interval. One30minute scale and one1minute gap, no sweep.',
        hypotheses=[
            dict(id='H1', question='Does signed prior30minute directional efficiency associate positively with subsequent30minute signed log price change?',
                mechanism='Persistent directional pressure may continue across nearby periods; the pressure itself is not identified in Last data.',
                x='(last close-first open)/sum(abs(each close-previous));first previous=first open',
                y='10000*log(response last close/response first open)',
                primary='Median of daily Spearman correlations over the six fixed clocks; report valid days and each day',
                auxiliary='Pooled and same-clock Spearman as diagnostics, plus continued/reversed/neutral counts. No ranking clocks.',
                continuation='Past net=0 excluded as direction undefined; future net=0 counted neutral; continuation fraction=continued/all past-nonzero events, including neutral outcomes.'),
            dict(id='H2', question='Does relative prior30minute RMS movement predict relative subsequent30minute RMS movement?',
                mechanism='Clustering of price-movement scale may help risk measurement, without predicting buy/sell direction.',
                x='Prior RMS / median prior5 sessions same-clock prior RMS',
                y='Response RMS / median prior5 sessions same-clock response RMS',
                primary='Median daily Spearman across six fixed clocks',
                fixed_forecast='Same-clock prior5 response RMS median * x; multiplier exponent/coefficient fixed1, not fitted',
                control='Same-clock prior5 response RMS median alone',
                forecast_diagnostic='For each day mean absolute error over six events, then equal-day mean improvement=controlMAE-fixedForecastMAE. Positive means smaller error.',
                auxiliary='Pooled/same-clock correlations, earlier5/recent5 summaries, leave-one-day-out mean improvement. No multiplier fitting.')],
        undefined='Flat close path yields undefined signed efficiency; zero reference median yields undefined normalized value/forecast; constant vectors yield undefined correlation, never zero-imputed.',
        aggregation='Unit of dependence is day, not60 independent events. Daily correlations n=6 are coarse. Report median/Q1/Q3/min/max/count, full daily values, earlier5/recent5, leave-one-day-out ranges. No p-values/significance claim.',
        consistency_gate=dict(
            H1='All10 daily correlations defined; overall,earlier5,recent5 daily-rho medians and every leave-one-day-out daily-rho median >0',
            H2='H1-style positive-rho consistency plus all60 forecast pairs defined and mean error improvement >0 overall,earlier5,recent5 and every leave-one-day-out mean',
            interpretation='A descriptive screening convention only, not statistical significance, causal proof, OOS success or strategy adoption. Gate miss does not authorize flipping to contrarian or retuning.'),
        budgets=dict(hypotheses=2, fixed_forecast_mappings=1, exploratory_reports=1,
                     native_runs=0, strategy_performance_runs=0, downloads=0, parameter_search=0),
        outcome_policy='All15 dates already consumed development data. This study consumes no untouched future dates; do not call recent5 OOS. Log both hypotheses even if negative.',
        causality='Point-in-time feature availability only. Association does not establish a causal market mechanism. Last response endpoints are not executable fills.',
        exclusions=previous['exclusions'], sources=previous['sources'],
        original_input_hashes=inputs, immutable_hashes=previous['immutable_hashes'],
        references=[
            dict(url='https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/research-guide',role='Hypothesis-first research, point-in-time availability and avoidance of repeated selection; not evidence these NQ hypotheses work'),
            dict(url='https://carmamaths.org/resources/jon/backtest2.pdf',role='Repeated-selection overfitting methodology; PBO not computed here')],
        stop='One registered study, report, dashboard ACK and repository publication. No automatic repeated same-data trials, threshold changes, strategy installation, scheduling or orders.',
        next_stage='Only if evidence warrants: separately specified pre-entry strategy/feature validation on data not used to select it. Existing Bollinger future reservation remains unchanged.')
    atomic(ROOT/PLAN, plan)
    ledger = read('research/campaign-data-analysis-ledger.json')
    require(not any(e['id'] == plan['id'] for e in ledger['entries']), 'Duplicate study id')
    ledger['entries'].append(dict(id=plan['id'], kind=plan['kind'], status='registered', plan=PLAN,
        plan_sha256=file_hash(ROOT/PLAN), hypotheses=2, native_runs=0, dates=dates,
        outcomes_inspected=False, prior_authorization=plan['authorization'], stop=plan['stop']))
    atomic(ROOT/'research/campaign-data-analysis-ledger.json', ledger)
    queue = read('research/evidence-work-queue.json')
    queue['tasks'].append(dict(id=plan['id'], kind=plan['kind'], status='registered', plan=PLAN,
                               native_budget=0, hypotheses=2))
    atomic(ROOT/'research/evidence-work-queue.json', queue)
    backlog = read('research/candidate-backlog.json')
    backlog['state_response_study'] = dict(id=plan['id'], status='registered', plan=PLAN,
                                          strategy_candidate=False, native_budget=0, hypotheses=2)
    atomic(ROOT/'research/candidate-backlog.json', backlog)
    print(dict(plan=PLAN, sha256=file_hash(ROOT/PLAN), study_days=len(plan['study_dates']), events=60))


if __name__ == '__main__':
    main()
