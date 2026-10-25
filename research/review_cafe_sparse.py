"""Existing-ledger review only; no native submissions or changed metrics."""
import json,hashlib,time
from datetime import datetime
from zoneinfo import ZoneInfo
from runner.core import ROOT,atomic,file_hash,Queue
from runner.assessment import ledger_evidence,additional_slippage_evidence
from dashboard.reporter import emit,post
from dashboard.server import validate_run
from research.finalize_gap_fade import publish

def main():
    output=ROOT/'research/cafe-sparse-review.json';assert not output.exists()
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text());rows=[];docs=[]
    for phase in ('development','recent','high-resolution'):
        p=ROOT/f'data/runner/cafe-{phase}-20261025.json'
        docs.extend((phase,p,d) for d in json.loads(p.read_text()))
    conditions=json.loads((ROOT/'research/cafe-condition-summary.json').read_text())
    for phase,path,d in docs:
        fee=5 if d['settings']['slippageTicks']==2 else 10
        pnl=[t['pnl']-fee*t['qty'] for t in d['trades']]
        if sum(pnl)<=0:continue
        rid='cafe-native-'+hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()[:24]
        snap=q.telemetry/(hashlib.sha256(rid.encode()).hexdigest()+'.json');run=json.loads(snap.read_text())
        assert run['metrics']['net']==sum(pnl) and run['metrics']['trades']==len(pnl)
        ledger=ledger_evidence(d['trades'],fee);days=[l.split()[1] for l in d['output'] if l.startswith('AUDIT ')]
        for day in days:ledger['daily_net'].setdefault(datetime.strptime(day,'%Y%m%d').date().isoformat(),0)
        rejected=[float(l.split('risk=')[1]) for l in d['output'] if l.startswith('SIZE_REJECT ')]
        cap=[v for v in rejected if v>300];other=[v for v in rejected if v<=300]
        variant=d['inputs']['Variant'];minutes=60 if variant==3 else d['inputs']['RangeMinutes']
        context=next(c for c in conditions if c['variant']==variant and c['range_minutes']==minutes)
        gains=sum(v for v in pnl if v>0);best=max([0]+pnl);bestday=max([0]+list(ledger['daily_net'].values()))
        a=dict(decision='deferred',reason='Positive but1-4observed trades;cost/fill duplicates add no independent evidence',sample_status='insufficient_sample_and_regime_coverage',permanent_discard=False,independent_oos=False,
            net_after_assumed_fee=sum(pnl),trade_count=len(pnl),ledger_evidence=ledger,
            largest_positive_share_of_gross_profit=best/gains if gains else None,largest_trade_share_of_net=best/sum(pnl),net_without_best_positive_day=sum(pnl)-bestday,
            additional_fill_cost_sensitivity=[additional_slippage_evidence(d['trades'],fee,t) for t in (2,4)],
            nominal_risk_cap=300,cap_basis='Research pre-submission estimate:(stopdistance+2points)*20+$10;not guaranteed loss ceiling',
            observed_risk_cap_rejections=len(cap),other_size_rejections=len(other),minimum_rejected_risk=min(cap) if cap else None,
            all_condition_counts=None,all_condition_counts_note='Legacy logs do not provide a complete filter partition;SIZE_REJECT risk>300 is directly counted,not all rejected signals',
            distinct_configuration_session_coverage=context['distinct_sessions'],configuration_active_sessions=context['active_sessions'],new_native_runs=0,
            next_action='Retain frozen rules and$300cap. Require separately scoped distinct-session/regime coverage;do not repeat old windows or loosen risk cap to manufacture entries. Missing July/earlier regimes remain unverified.')
        run['params'].setdefault('assessment_history',[]).append(dict(recorded_at=time.time(),assessment=run['params'].get('assessment'),status=run['status'],reason=run['reason']))
        run['params']['assessment']=a;validate_run(run);emit(run,q.telemetry);assert post(config['url'],'/api/runs',run,config['token']).get('ok') is True;q.control('ack:'+snap.name,file_hash(snap))
        rows.append(dict(run_id=rid,phase=phase,inputs=d['inputs'],settings=d['settings'],original_metrics=run['metrics'],assessment=a,trades=d['trades'],source_ledger_sha256=file_hash(path),ack=True))
    assert len(rows)==12
    available=set()
    for r in json.loads((ROOT/'research/recent-tick-audit-20261025.json').read_text()):
        available.update(s['date'].replace('-','') for s in r['sessions'] if s['minutes']==390 and not s['missingMinutes'])
    available.update(r['date'].replace('-','') for r in json.loads((ROOT/'research/nr7-history-chunk1-decoded.json').read_text()))
    coverage=[]
    for c in conditions:
        if c['variant'] not in (2,3):continue
        seen={s['date'] for s in c['sessions']}
        coverage.append(dict(variant=c['variant'],effective_range_minutes=c['range_minutes'],evaluated_dates=sorted(seen),available_but_not_evaluated_dates=sorted(available-seen),resume_condition='Dates are available but insufficient alone to establish broader regimes;first verify full indicator ETHwarmup and classify predeclared session regimes without candidate PnL. No blind native date expansion.',full_filter_counter_sessions=c['instrumented_sessions'],legacy_size_rejections=c['size_rejections']))
    next_action='CafeRange retained as sparse/constraint-limited;12ledger reviews ACKed,0native repeats. Plan broader regime/ETHcoverage before future extension under unchanged$300cap. Select separately preregistered public-source candidate;RSI/Bollinger retained;OFIclosed;Playbackblock unchanged.'
    atomic(output,dict(rows=rows,coverage=coverage,review_acks=12,new_native_runs=0,independent_configurations=3,cost_and_fill_duplicates=True,limitations=['Counterfactual returns of risk-rejected signals unknown','Complete legacy filter counts unknown','Observed historical dates not independent OOS','No evidence of maximum8contract or account-equity compliance fromsinglecontract closedledgers'],next_action=next_action))
    p=ROOT/'research/candidate-backlog.json';b=json.loads(p.read_text())
    c=next(c for c in b['candidates'] if c['id']=='cafe-positive-data-extension');c.update(status='deferred_sample_and_constraint_coverage',latest_evidence='research/cafe-sparse-review.json',next_action=next_action)
    for c in b['candidates']:
        if c['id']=='nr7-history-extension-v1':c.update(status='deferred_sparse_sample_adoption_unmet',sample_status='1trade_insufficient',next_action='Preserve negative finite result;no family rejection. Further testing only on separately registered distinct regimes with actual NR7 setups;no same-date rerun or lookback tuning.')
    b['next_action']=next_action;atomic(p,b)
    p=ROOT/'research/evidence-work-queue.json';b=json.loads(p.read_text())
    for t in b['tasks']:
        if t['id']=='cafe-broader-constraint-coverage-review':t.update(status='completed',evidence='research/cafe-sparse-review.json',next_action=next_action)
    b['tasks'].append(dict(id='cafe-distinct-regime-eth-feasibility',candidate='cafe-positive-data-extension',kind='coverage-feasibility',status='deferred',next_action=coverage[0]['resume_condition'],evidence='research/cafe-sparse-review.json'))
    b['next_action']=next_action;atomic(p,b)
    # Add sample status without changing the observed NR7 performance decision.
    p=ROOT/'data/runner/nr7-history-extension/state.json';s=json.loads(p.read_text())
    for r in s['experiments'].values():
        r.setdefault('assessment_history',[]).append(dict(at=time.time(),assessment=dict(r['assessment'])))
        r['assessment'].update(sample_status='insufficient_one_unique_trade',research_disposition='deferred_sparse_sample',additional_evaluation_condition='Distinct preregistered regimes with actual NR7 setup exposure;no retune/no same-window repeat;not family rejection');publish(r,q,config)
    atomic(p,s);atomic(ROOT/'research/nr7-history-extension-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','assessment_history','ack')} for r in s['experiments'].values()])
    print(json.dumps(dict(cafe_review_acks=12,nr7_metadata_acks=2,new_native_runs=0,representative=[dict(variant=r['inputs']['Variant'],range=r['inputs']['RangeMinutes'],trades=r['assessment']['trade_count'],net=r['assessment']['net_after_assumed_fee'],without_best=r['assessment']['ledger_evidence']['net_without_best_positive'],extra4=r['assessment']['additional_fill_cost_sensitivity'][1]['net'],risk_rejections=r['assessment']['observed_risk_cap_rejections']) for r in rows if r['phase']=='development' and r['settings']['slippageTicks']==2])),flush=True)

if __name__=='__main__':main()
