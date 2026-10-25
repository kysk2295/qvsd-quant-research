"""One preregistered descriptive analysis of preserved rawLast minute bars."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from runner.core import ROOT, atomic, file_hash
from research.market_state_metrics import bucket_metrics, distribution, validate_minutes

PLAN = 'research/nq-market-state-plan.json'
PLAN_SHA256 = '8d0f6709d1e78e194979be419a5e404beb7fecca51f7d6bac1cad2ecba653666'
RESULT = 'research/nq-market-state-baseline.json'
METRICS = ('rms_log_move_bps', 'volume_per_minute', 'directional_efficiency', 'five_minute_reversal_fraction', 'net_points')


def read(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def verify_hashes(plan):
    require(file_hash(ROOT/PLAN) == PLAN_SHA256, 'Registered plan changed')
    for path, digest in {**plan['original_input_hashes'], **plan['immutable_hashes']}.items():
        require(file_hash(ROOT/path) == digest, 'Preserved input changed: ' + path)


def main():
    require(not (ROOT/RESULT).exists(), 'Report already exists; no routine recalculation')
    plan = read(PLAN)
    verify_hashes(plan)
    ledger = read('research/campaign-data-analysis-ledger.json')
    registered = [e for e in ledger['entries'] if e['id'] == plan['id']]
    require(len(registered) == 1 and registered[0]['status'] == 'registered' and
            registered[0]['plan_sha256'] == PLAN_SHA256, 'Registration missing or inconsistent')
    cache = read(plan['cached_ohlcv'])
    require(cache['complete'] is True and cache['timezone'] == plan['timezone'], 'Cache metadata mismatch')
    require(sorted(cache['sessions']) == plan['dates'], 'Cache dates changed')
    require(cache['sources'] == plan['sources'], 'Source lineage changed')
    audits = {}
    for item in read('research/recent-tick-audit-20261025.json'):
        for session in item['sessions']:
            date = session['date']
            require(date not in audits, 'Duplicate audit date')
            audits[date] = dict(session, source_sha256=item['sha256'])
    context = read('research/cafe-regime-inventory.json')['sessions']
    verified_sources, daily, daily_context = [], [], []
    for source in plan['sources']:
        require(file_hash(Path(source['path'])) == source['sha256'], 'Raw source changed: ' + source['date'])
        verified_sources.append(dict(source, verified=True))
    for date in plan['dates']:
        group = 'recent' if date in plan['recent_dates'] else 'baseline'
        minutes = cache['sessions'][date]
        bars = validate_minutes(minutes, 570, 960)
        audit = audits[date]
        source = next(s for s in plan['sources'] if s['date'] == date)
        require(audit['minutes'] == 390 and audit['missingMinutes'] == [] and
                audit['source_sha256'] == source['sha256'], 'Raw audit mismatch: ' + date)
        volume = sum(b['volume'] for b in bars)
        require(volume == audit['rthVolume'], 'Daily volume mismatch: ' + date)
        reused = context[date]
        require(reused['source'] == 'rawLast', 'Noncomparable context source: ' + date)
        observed_range = max(b['high'] for b in bars) - min(b['low'] for b in bars)
        observed_net = bars[-1]['close'] - bars[0]['open']
        require(math.isclose(observed_range, reused['rth_range_points'], abs_tol=1e-8, rel_tol=0) and
                math.isclose(observed_net, reused['open_close_points'], abs_tol=1e-8, rel_tol=0),
                'Existing daily context/cache disagreement: ' + date)
        daily_context.append(dict(date=date, group=group, rth_volume=volume,
                                  rth_range_points=reused['rth_range_points'],
                                  open_close_points=reused['open_close_points'],
                                  context_source='research/cafe-regime-inventory.json'))
        for bucket in plan['buckets']:
            segment = [minutes[str(m)] for m in range(bucket['start'], bucket['end'])]
            metrics = bucket_metrics(segment)
            require(metrics['directional_efficiency'] is None or 0 <= metrics['directional_efficiency'] <= 1,
                    'Efficiency outside bounds')
            daily.append(dict(date=date, group=group, bucket=bucket['label'],
                              available_after_et=f"{bucket['end']//60:02d}:{bucket['end']%60:02d}", **metrics))
    comparisons = []
    for bucket in plan['buckets']:
        groups = {}
        for group in ('baseline', 'recent'):
            rows = [r for r in daily if r['group'] == group and r['bucket'] == bucket['label']]
            groups[group] = {metric: distribution([r[metric] for r in rows]) for metric in METRICS}
            groups[group]['reversal_pair_counts'] = dict(
                reversals=sum(r['five_minute_reversals'] for r in rows),
                eligible=sum(r['five_minute_eligible_pairs'] for r in rows),
                excluded_zero=sum(r['five_minute_zero_excluded_pairs'] for r in rows),
                total=sum(r['five_minute_total_pairs'] for r in rows),
                role='Coverage counts only; fraction summaries above weight sessions equally, not pairs.')
        comparisons.append(dict(bucket=bucket['label'], **groups))
    context_distributions = {
        group: {metric: distribution([d[metric] for d in daily_context if d['group'] == group])
                for metric in ('rth_volume', 'rth_range_points', 'open_close_points')}
        for group in ('baseline', 'recent')}
    verify_hashes(plan)
    result = dict(id=plan['id'], label=plan['label'], created_at_utc=datetime.now(timezone.utc).isoformat(),
                  plan=PLAN, plan_sha256=PLAN_SHA256, instrument=plan['instrument'], timezone=plan['timezone'],
                  baseline_dates=plan['baseline_dates'], recent_dates=plan['recent_dates'],
                  metrics_definition=plan['metrics'], aggregation=plan['aggregation'],
                  quantiles='Type7 linear interpolation at (n-1)*p; equal weight per session; IQR is observed dispersion, not confidence interval.',
                  daily_buckets=daily, bucket_distributions=comparisons,
                  reused_daily_context=daily_context, daily_context_distributions=context_distributions,
                  quality=dict(passed=True, sessions=15, minutes=5850, buckets=90,
                               source_hashes=verified_sources, audit_volume_match=True, existing_context_match=True,
                               no_missing_minutes=True, positive_tick_aligned_ohlc=True, no_fill_forward=True),
                  original_input_hashes=plan['original_input_hashes'], immutable_hashes=plan['immutable_hashes'],
                  analysis_code_hashes={p:file_hash(ROOT/p) for p in [
                      'research/analyze_market_state.py','research/market_state_metrics.py','tests/test_market_state_metrics.py']},
                  native_runs=0, downloads=0, performance_tests=0, optimization_trials=0,
                  independent_oos=False, strategy_defined=False, exclusions=plan['exclusions'],
                  limitations=[
                      'Only15 adjacent development sessions of one contract; latest usable date2026-10-22. Not broad regime evidence or a current live-market assessment.',
                      'Recent5/preceding10 descriptive comparison was fixed before bucket analysis, but dates were already used for prior strategy development; not independent OOS.',
                      'Weekday composition is balanced; macro events, serial dependence and news effects are not controlled.',
                      'Minute close paths omit intraminute movement; RMS is uncentered, efficiency depends on sampling interval.',
                      'Five-minute sign changes do not imply profitable mean reversion after entry, stop, spread and slippage.',
                      'Volume is unsigned reported Last contracts. Upstream quotes exist, but spread, aggressor direction, queue and executable prices are not assessed here.',
                      'Cached ordering within equal source timestamps is inherited; exchange sequence not established.',
                      'No after-fee strategy return, stop/target, trading time filter, parameter threshold or adopted strategy follows from these metrics.'],
                  causal_availability=[
                      dict(feature='Completed bucket metrics', available='After bucket end in ET', restriction='Not usable to select trades earlier in that same bucket'),
                      dict(feature='Full RTH range/open-close/context', available='After16:00 ET', restriction='Not an opening-time trend/range label'),
                      dict(feature='Running volatility/volume/price-position/flow', available='Only using events at or before decision time', restriction='Not computed or validated as features in this report')],
                  stop=plan['stop'])
    atomic(ROOT/RESULT, result)
    print(json.dumps(dict(result=RESULT, sessions=15, minutes=5850, buckets=90, quality_passed=True, native_runs=0)))


if __name__ == '__main__':
    main()
