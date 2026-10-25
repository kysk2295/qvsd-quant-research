"""Register one data-only descriptive analysis before computing new statistics."""
import json
from datetime import datetime,timezone
from runner.core import ROOT,atomic,file_hash

def main():
    path=ROOT/'research/nq-market-state-plan.json'
    if path.exists():raise RuntimeError('Analysis plan already registered; inspect existing state, do not overwrite')
    cachepath='research/stochastic-coverage.json';cache=json.loads((ROOT/cachepath).read_text())
    dates=sorted(cache['sessions']);assert len(dates)==15 and dates[-1]=='2026-10-22'
    assert all(d<'2026-10-25' for d in dates)
    protected=json.loads((ROOT/'research/equity-audit-immutable-inputs.json').read_text())
    assert all(file_hash(ROOT/p)==h for p,h in protected.items())
    inputs={p:file_hash(ROOT/p) for p in [cachepath,'research/cafe-regime-inventory.json','research/recent-tick-audit-20261025.json','research/campaign-trial-registry.json','research/campaign-search-control.json','research/bollinger-prospective-plan.json']}
    plan=dict(id='nq-market-state-existing-20261025',registered_at_utc=datetime.now(timezone.utc).isoformat(),
        purpose='One descriptive baseline of existing NQ market states; no strategy, PnL, threshold search or independent validation.',
        label='개발자료 시장 상태 분석',instrument='NQ DEC26',timezone='America/New_York',session='09:30 inclusive–16:00 exclusive',
        dates=dates,baseline_dates=dates[:-5],recent_dates=dates[-5:],
        split_rule='Latest5 complete comparable cached sessions versus preceding10; each weekday appears1 vs2 times. Fixed before new bucket statistics; not chosen on returns.',
        sources=cache['sources'],cached_ohlcv=cachepath,original_input_hashes=inputs,immutable_hashes=protected,
        buckets=[dict(label=label,start=start,end=end) for label,start,end in [
            ('09:30–10:00',570,600),('10:00–10:30',600,630),('10:30–11:30',630,690),
            ('11:30–13:30',690,810),('13:30–15:30',810,930),('15:30–16:00',930,960)]],
        metrics=dict(rms_log_move_bps='10000*sqrt(mean(log(close/previous)^2));first previous is bucket first open,then previous minute close;drift included,not centeredSD',
            volume_per_minute='Sum reported Last trade volume / bucket minute count; unsigned recorded contract volume,not aggressor pressure',
            directional_efficiency='abs(last close-first open)/sum(abs(close-previous));same within-bucket path,undefined if path0',
            five_minute_reversal_fraction='Sign changes between adjacent nonoverlapping5minute close movements using firstopen then preceding5minclose; exclude pairs with zero move; never span days/buckets',
            context='Whole-session high-low range and open-close move reused from cafe-regime-inventory and checked against cache;bucket netpoints endpoint context only'),
        aggregation='Calculate each day/bucket; report median,Q1,Q3,min,max and counts across sessions. No pooled-minute independence assumption,p-values,winner selection or profitable hours.',
        quality=['Input hashes unchanged','15dates,each390distinct sequential RTH minutes','Finite positive tick-aligned OHLC; high/low contain open/close;positive integer Last volume',
            'Cached daily volume equals prior raw tick audit','Existing whole-session range/net agree with cache','Raw source paths and SHA256 retained; preserved source hashes verified',
            'Reject missing/changed dates;no fill-forward or provider substitution'],
        reuse=['Cached5850minute rawLast OHLCV and volume;no raw reaggregation','Existing whole-session descriptive range/net;no repeat strategy metrics'],
        exclusions=['Yahoo5minute continuous proxy','Native-only minute Sep28–Oct1 context','Sep23–25 separate sparse block','Oct23 decoder/header disagreement','FutureOct26–Nov6'],
        causality='Completed-bucket/full-day statistics available only after their end. Final daily range/VWAP/day labels cannot filter earlier trades. This report defines no trading rule.',
        budgets=dict(analysis_reports=1,new_native_runs=0,new_downloads=0,performance_tests=0,parameter_search=0),
        stop='Stop after one validated report and dashboard ACK,or on input/quality failure. No automatic new hypothesis or repetition.',
        resume='Only separately scoped work after a documented data/source/state change;future frozen performance plan and native budget0 remain unchanged.')
    atomic(path,plan)
    ledgerpath=ROOT/'research/campaign-data-analysis-ledger.json'
    ledger=json.loads(ledgerpath.read_text()) if ledgerpath.exists() else dict(kind='Supplemental non-performance campaign ledger',frozen_performance_registry='research/campaign-trial-registry.json',entries=[])
    assert not any(e['id']==plan['id'] for e in ledger['entries'])
    ledger['entries'].append(dict(id=plan['id'],status='registered',plan=str(path.relative_to(ROOT)),plan_sha256=file_hash(path),purpose=plan['purpose'],dates=dates,source_hashes=cache['sources'],metrics=plan['metrics'],buckets=plan['buckets'],quality=plan['quality'],stop=plan['stop'],native_runs=0))
    atomic(ledgerpath,ledger)
    p=ROOT/'research/evidence-work-queue.json';queue=json.loads(p.read_text())
    queue['tasks'].append(dict(id=plan['id'],kind='data-only-market-state',status='registered',plan='research/nq-market-state-plan.json',native_budget=0,stop=plan['stop']))
    atomic(p,queue)
    p=ROOT/'research/candidate-backlog.json';backlog=json.loads(p.read_text())
    backlog['market_state_analysis']=dict(id=plan['id'],status='registered',plan='research/nq-market-state-plan.json',strategy_candidate=False,new_native_budget=0,stop=plan['stop'])
    atomic(p,backlog)
    print(json.dumps(dict(plan_sha256=file_hash(path),sessions=len(dates),baseline=dates[:-5],recent=dates[-5:],native_runs=0)))

if __name__=='__main__':main()
