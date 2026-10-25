"""Review Oct6 historical extension and quote-touch diagnostics; no submissions."""
import csv,json,math
from datetime import datetime,time
from zoneinfo import ZoneInfo
from runner.core import ROOT,atomic,file_hash,Queue
from runner.research_lifecycle import Lifecycle
from research.finalize_gap_fade import publish

def main():
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
    coverage=json.loads((ROOT/'research/ofi-oct6-coverage.json').read_text());assert file_hash(coverage['path'])==coverage['sha256']
    with open(coverage['path']) as f:features={int(x['end_utc_ns']):x for x in csv.DictReader(f,delimiter=';')}
    path=ROOT/'data/runner/ofi-oct6/state.json';state=json.loads(path.read_text());rows=sorted(state['experiments'].values(),key=lambda r:r['request']['slippageTicks'])
    assert len(rows)==2;ledgers=[];tuples=[];results=[]
    next_action='Freeze OFI threshold10/lag60s/hold5bars. No more local complete untested RTH quote dates. Resume only with distinct valid recorded sessions and preregistered finite budget; Oct6 is historical, not prospective. Before execution-valid latency claims require subsecond native execution timestamps and causal order/stop path simulation within allowed Backtest/offline scope.'
    for r in rows:
        assert r['ack'] and r['assessment']['decision']!='execution_error'
        trades=r['doc']['trades'];signals=[s for s in r['doc']['output'] if s.startswith('SIGNAL ')]
        assert len(trades)==len(signals)==4;matched=[];prev=None
        for s,t in zip(signals,trades):
            p=s.split();st=datetime.fromisoformat(p[1]).replace(tzinfo=ZoneInfo('America/New_York'));v=dict(x.split('=',1) for x in p[2:]);end=int(v['featureEnd']);last=int(v['lastSource']);f=features[end]
            assert end==int(st.timestamp())*10**9-60*10**9 and 0<last<end and last==int(f['last_source_ns'])
            score=float(f['ofi'])/float(f['mean_depth']);assert f['eligible']=='1' and abs(score)>=10 and math.isclose(score,float(v['score']),rel_tol=1e-12)
            assert 0<float(f['spread_ticks'])<=4 and float(f['spread_ticks'])==float(v['spread'])
            assert v['side']==('L' if score>0 else 'S') and t['entryName']==v['side'] and t['side']==('Long' if score>0 else 'Short') and t['qty']==1
            entry=datetime.fromisoformat(t['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'));exit=datetime.fromisoformat(t['exitTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
            assert entry.date().isoformat()==exit.date().isoformat()=='2026-10-06' and 0<=(entry-st).total_seconds()<=60 and entry<=exit
            assert time(9,40)<=st.time()<=time(15,25) and exit.time()<=time(15,56) and (prev is None or entry>=prev);prev=exit
            assert abs(t['pnl']-(t['exitPrice']-t['entryPrice'])*20*(1 if score>0 else -1))<1e-6
            matched.append(dict(signal=s,feature=f,trade=t))
        tuples.append([(t['entryTime'],t['entryPrice'],t['exitTime'],t['exitPrice'],t['side']) for t in trades])
        r['assessment'].update(causal_feature_match=True,native_signal_fill_match=True,independent_oos=False,adoption_gate='deferred_single_session',next_action=next_action,quote_cost_evidence='research/ofi-touch-cost-audit.json')
        ledgers.append(dict(run_id=r['run_id'],native_id=r['native_id'],matched=matched,native_response_sha256=file_hash(path.parent/(r['key']+'.native.json'))))
        results.append(dict(slippage=r['request']['slippageTicks'],trades=4,net=r['assessment']['net_after_assumed_fee'],additional4tick_net=next(s['net'] for s in r['assessment']['additional_fill_cost_sensitivity'] if s['additional_ticks_per_fill']==4)))
    assert tuples[0]==tuples[1]
    for r in rows:
        r['assessment']['native_fill_cost_limitation']='Requested2/4tick native fills identical; net difference external fees only. Additional adverse ticks arithmetic.';publish(r,q,config)
    atomic(path,state);atomic(ROOT/'research/ofi-oct6-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows]);atomic(ROOT/'research/ofi-oct6-ledgers.json',ledgers)
    touch=json.loads((ROOT/'research/ofi-touch-cost-audit.json').read_text())
    touch['timestamp_precision_limitation']='Native serialized entry/exit timestamps are whole seconds. Strictly preceding quote may precede true execution by almost1second; +100/+1000ms are offsets from serialized timestamps, not measured routing delays. No exact execution-cost estimate or validated alternate PnL.'
    touch['zero_offset_spread_above4ticks']={field:sum(next(s for s in r['scenarios'] if s['delay_ms']==0)[field+'_spread_ticks']>4 for r in touch['evidence']) for field in ('entry','exit')}
    atomic(ROOT/'research/ofi-touch-cost-audit.json',touch)
    for segment in ('early','late'):
        p=ROOT/f'data/runner/ofi-{segment}/state.json';s=json.loads(p.read_text())
        for r in s['experiments'].values():
            r['assessment'].update(quote_cost_evidence='research/ofi-touch-cost-audit.json',quote_cost_status='diagnostic_only_seconds_precision_and_unchanged_exit_path',execution_spread_gate_limitation='Frozen<=4tick gate uses feature ending60s before decision; not current executable spread. Two of48 entry observations exceeded4ticks.',next_action=next_action)
            publish(r,q,config)
        atomic(p,s);atomic(ROOT/f'research/ofi-{segment}-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in s['experiments'].values()])
    summary=dict(native_runs=2,result_acks=2,review_metadata_acks=6,extension_unique_trades=4,total_unique_trades=52,total_sessions=13,independent_oos=False,results=results,
        combined_base_net=1305,combined_high_fee_net=1045,combined_base_extra4tick_net=-775,combined_high_fee_extra4tick_net=-1035,
        existing48trade_cost_diagnostic=touch['scenarios'],timestamp_precision_limitation=touch['timestamp_precision_limitation'],next_action=next_action)
    atomic(ROOT/'research/ofi-followup-summary.json',summary)
    p=ROOT/'research/candidate-backlog.json';b=json.loads(p.read_text());c=next(c for c in b['candidates'] if c['id']=='ofi-lagged-v1')
    c.update(extension_evidence='research/ofi-followup-summary.json',extension_budget=dict(completed=2,total=2),unique_trades=52,sessions=13,next_action=next_action,status='deferred_cost_concentration_execution_evidence');b['next_action']=next_action;atomic(p,b)
    p=ROOT/'research/evidence-work-queue.json';b=json.loads(p.read_text())
    for t in b['tasks']:
        if t['id']=='ofi-future-quote-coverage':t.update(next_action=next_action,local_inventory='Oct6 now evaluated; Oct11/18 Sunday; Oct23 known corrupt excluded; no future sessions as of Oct25.')
    atomic(p,b)
    Lifecycle().update('idle','Oct6 extension2runs/2ACKs,4trades,+700/+680.52unique trades total.48trade quote-cost diagnostic ACKed; coarse timestamps prevent execution claims. Next:distinct quote coverage and timing evidence.',None)
    print(json.dumps({k:v for k,v in summary.items() if k!='existing48trade_cost_diagnostic'},indent=2))

if __name__=='__main__':main()
