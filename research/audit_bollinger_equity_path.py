"""Audit saved52trades against preserved Last data; no strategy execution."""
import json,calendar,time
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import numpy as np
from runner.core import ROOT,atomic,file_hash
from research.last_equity_bounds import FillWindow,audit_path

IMMUTABLE=['research/bollinger-return-results.json','research/bollinger-return-summary.json','research/bollinger-return-ledgers.json','research/bollinger-return-manifest.json','research/bollinger-prospective-plan.json','research/campaign-search-control.json','research/campaign-trial-registry.json','data/runner/bollinger-return/state.json']
def ns(stamp):
    dt=datetime.fromisoformat(stamp).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(timezone.utc)
    return calendar.timegm(dt.utctimetuple())*10**9+dt.microsecond*1000

def load_last(path):
    times=[];prices=[];previous=None;base=0
    with open(path,encoding='ascii') as f:
        for line in f:
            stamp,price,volume=line.strip().split(';');second=stamp[:15]
            if second!=previous:
                previous=second;base=calendar.timegm(datetime.strptime(second,'%Y%m%d %H%M%S').timetuple())*10**9
            times.append(base+int(stamp[16:])*100);prices.append(float(price))
    return np.asarray(times,dtype=np.int64),np.asarray(prices,dtype=float)

def main():
    target=ROOT/'research/bollinger-equity-path-audit.json';assert not target.exists()
    frozen={p:file_hash(ROOT/p) for p in IMMUTABLE};atomic(ROOT/'research/equity-audit-immutable-inputs.json',frozen)
    state=json.loads((ROOT/'data/runner/bollinger-return/state.json').read_text());rows=sorted(state['experiments'].values(),key=lambda r:r['request']['slippageTicks']);trades=rows[0]['doc']['trades']
    keys=('entryTime','entryPrice','exitTime','exitPrice','qty','side')
    assert [[t[k] for k in keys] for t in trades]==[[t[k] for k in keys] for t in rows[1]['doc']['trades']]
    sources=json.loads((ROOT/'research/bollinger-return-summary.json').read_text())['raw_sources'];bydate={};windows=[]
    for t in trades:
        dt=datetime.fromisoformat(t['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'));day=dt.date().isoformat()
        window=FillWindow(ns(t['entryTime']),ns(t['entryTime'])+10**9,ns(t['exitTime']),ns(t['exitTime'])+10**9,t['entryPrice'],t['exitPrice'],1 if t['side']=='Long' else -1,t['qty'])
        assert abs((window.exit_price-window.entry_price)*window.side*20*window.qty-t['pnl'])<1e-7
        bydate.setdefault(day,[]).append((t,window));windows.append(window)
    all_ts=[];all_px=[];daily=[];precise=[];last_counts={};folder=ROOT/'data/runner/bollinger-equity-path';folder.mkdir(exist_ok=True)
    diagnostic=json.loads((ROOT/'research/execution-clock-audit.json').read_text());assert diagnostic['baseline_trade_match']
    for source in sources:
        day=source['date'];assert file_hash(source['path'])==source['sha256']
        ts,prices=load_last(source['path']);assert np.all(np.diff(ts)>=0) and np.all(prices>0)
        daytrades=[w for _,w in bydate[day]];earliest=daytrades[0].entry_lo;latest=daytrades[-1].exit_hi
        a=max(0,int(np.searchsorted(ts,earliest,'left'))-1);b=min(len(ts),int(np.searchsorted(ts,latest,'right'))+1)
        ts=ts[a:b];prices=prices[a:b];all_ts.append(ts);all_px.append(prices);last_counts[day]=len(ts)
        for fee in (5,10):
            r=audit_path(ts,prices,daytrades,fee);path=r.pop('path');r.update(date=day,fee=fee)
            np.savez_compressed(folder/(day+'-fee'+str(fee)+'.npz'),**path);daily.append(r)
        if day=='2026-10-06':
            refined=[];assert len(diagnostic['pairs'])==len(daytrades)==4
            for (trade,coarse),pair in zip(bydate[day],diagnostic['pairs']):
                entry=pair['entry'];exit=pair['exit'];assert entry['price']==trade['entryPrice'] and exit['price']==trade['exitPrice']
                e=entry['utc_ns'];x=exit['utc_ns'];assert coarse.entry_lo<=e<coarse.entry_hi and coarse.exit_lo<=x<coarse.exit_hi
                refined.append(FillWindow(e,e,x,x,coarse.entry_price,coarse.exit_price,coarse.side,coarse.qty))
            for fee in (5,10):
                r=audit_path(ts,prices,refined,fee);r.pop('path');coarse=next(d for d in daily if d['date']==day and d['fee']==fee)
                assert r['holding_path_drawdown_lower']+1e-7>=coarse['holding_path_drawdown_lower'] and r['holding_path_drawdown_upper']<=coarse['holding_path_drawdown_upper']+1e-7
                precise.append(dict(date=day,fee=fee,refined=r,coarse_drawdown_bounds=[coarse['holding_path_drawdown_lower'],coarse['holding_path_drawdown_upper']],note='Only4previouslylogged diagnostictrades;equal-time tickorder stillunresolved;no change to original52trade ledger'))
        print(json.dumps(dict(date=day,last_price_points=len(ts),audited_trades=len(daytrades))),flush=True)
    ts=np.concatenate(all_ts);prices=np.concatenate(all_px);aggregates=[]
    for row,fee in zip(rows,(5,10)):
        r=audit_path(ts,prices,windows,fee);path=r.pop('path');dest=folder/('aggregate-fee'+str(fee)+'.npz');np.savez_compressed(dest,**path)
        assert abs(r['net']-row['assessment']['net_after_assumed_fee'])<1e-7 and r['closed_trade_drawdown']==row['assessment']['closed_trade_drawdown']
        ddays=[d for d in daily if d['fee']==fee];r.update(run_id=row['run_id'],fee=fee,path_archive=str(dest),path_archive_sha256=file_hash(dest),worst_closed_day=min(d['net'] for d in ddays),worst_intraday_loss_from_day_start_lower=max(d['worst_loss_from_start_lower'] for d in ddays),worst_intraday_loss_from_day_start_upper=max(d['worst_loss_from_start_upper'] for d in ddays));aggregates.append(r)
    gate=[]
    for day,pairs in bydate.items():
        realized=0;entry_checks=[]
        for t,w in pairs:
            entry_checks.append(dict(entry_time=t['entryTime'],before_entry_realized_after10fee=realized,entry_permitted=realized>-900));assert realized>-900
            realized+=t['pnl']-10
        gate.append(dict(date=day,entry_checks=entry_checks,day_realized_after10fee=realized,realized_overshoot_beyond900=max(0,-realized-900),gate_is_hard_loss_cap=False))
    assert all(file_hash(ROOT/p)==h for p,h in frozen.items())
    report=dict(created_at=time.time(),native_runs=0,strategy_rules_changed=False,unique_existing_trades=52,raw_sources=sources,source_last_points=last_counts,aggregates=aggregates,daily=daily,precise_diagnostic_subset=precise,realized_entry_gate=gate,immutable_input_hashes=frozen,immutable_hashes_preserved=True,
        valuation='1NQ marked to observedLast;fee split equally at entry/exit;flat endpoints identical to original per-roundtrip-fee ledger. Not bidask liquidation or liveaccount.',
        uncertainty='Original timestamps floor toseconds;possibleholding enlarged through nextsecond boundary. LowerDD uses only assuredopen ticks andclosedanchors;upperDD allows worstcoincident envelope andneed not be attainable. Even exactfractions do not resolve tickorderat same timestamp.',
        limits=['Bounds conditional on preservedLast stream andfixedoriginalfills;exchange-levelmissingprints unbounded','No reconstructedfull precision for other48trades','No changed orderpath,stoptrigger,queue,spreadorimpact simulation','No competitionaccount risk certification;submissiondeadline separatefromNov7researchdecision'],
        cost_scope='Fee allocation changes whenfeesenterMTM;doesnot change finalnet. Additionaltickstress remains separate arithmetic andisnot included as changedexecutionpath.')
    atomic(target,report);print(json.dumps(dict(aggregate=[{k:r[k] for k in ('fee','net','closed_trade_drawdown','holding_path_drawdown_lower','holding_path_drawdown_upper','worst_closed_day','worst_intraday_loss_from_day_start_lower','worst_intraday_loss_from_day_start_upper')} for r in aggregates],immutable_hashes_preserved=True)),flush=True)

if __name__=='__main__':main()
