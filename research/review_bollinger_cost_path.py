"""Existing-ledger and documented-engine review; zero native submissions."""
import json,time
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from runner.core import ROOT,atomic,file_hash,Queue
from research.finalize_gap_fade import publish

def main():
    target=ROOT/'research/bollinger-cost-path-review.json';assert not target.exists()
    folders=['bollinger-return','macd-cross','ofi-early','ofi-late','ofi-oct6','ofi-oct5','ofi-oct2'];pairs=[];allrows=[]
    def et(stamp):return datetime.fromisoformat(stamp).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
    keys=('entryTime','entryPrice','exitTime','exitPrice','qty','side')
    for folder in folders:
        path=ROOT/'data/runner'/folder/'state.json';s=json.loads(path.read_text());rows=sorted(s['experiments'].values(),key=lambda r:r['request']['slippageTicks']);assert len(rows)==2 and all(r.get('ack') for r in rows)
        tuples=[[tuple(t[k] for k in keys) for t in r['doc']['trades']] for r in rows]
        assert tuples[0]==tuples[1]
        a,b=rows;assert a['doc']['settings']['slippageTicks']==2 and b['doc']['settings']['slippageTicks']==4
        for r in rows:
            settings=r['doc']['settings'];assert settings['fillResolution']=='High' and settings['fillResolutionType']=='Tick' and settings['fillResolutionValue']==1 and settings['includeCommission'] is False
        trades=a['doc']['trades'];daily=Counter(et(t['entryTime']).date().isoformat() for t in trades)
        pairs.append(dict(folder=folder,run_ids=[r['run_id'] for r in rows],trades=len(trades),identical_fill_tuples=True,requested_slippage=[2,4],actual_settings_readback=[r['doc']['settings'] for r in rows],daily_entry_counts=dict(daily),all_active_days_at_four_cap=all(n==4 for n in daily.values()),latest_entry_et=max(et(t['entryTime']).strftime('%H:%M:%S') for t in trades) if trades else None,source_state_sha256=file_hash(path)))
        allrows.extend((path,s,r) for r in rows)
    bb=[r for p,s,r in allrows if p.parent.name=='bollinger-return'];figures=[]
    for r in bb:
        fee=5 if r['request']['slippageTicks']==2 else 10;trades=r['doc']['trades'];daily={}
        for t in trades:
            day=et(t['exitTime']).date().isoformat();daily[day]=daily.get(day,0)+t['pnl']-fee*t['qty']
        net=sum(daily.values());best=max(daily.values());worst=min(daily.values())
        figures.append(dict(run_id=r['run_id'],fee=fee,net=net,daily_net=daily,worst_day=worst,worst_day_dates=[d for d,v in daily.items() if v==worst],best_day_removed=net-best,days_below_minus900=[d for d,v in daily.items() if v<-900],extra2ticks_net=net-20*len(trades),extra4ticks_net=net-40*len(trades),additional_ticks_per_fill_break_even=net/(10*len(trades)),maximum_reported_trade_mae_points=max(t['mae'] for t in trades),account_mark_to_market_drawdown=None,account_path_note='Per-trade MAE and second-resolution timestamps do not reconstruct continuous account-equity path;do not relabel closedDD as intratrade risk'))
    addon=Path.home()/'Documents/NinjaTrader 8/bin/Custom/AddOns/NT8Bridge.Backtest.cs';code=addon.read_text(encoding='utf-8-sig')
    assert 's.Slippage' in code and 'Slippage rejected' in code
    report=dict(created_at=time.time(),native_runs=0,engine_sources=[dict(url='https://static.ninjatrader.com/support/helpGuides/nt8/understanding_historical_fill_.htm',finding='Slippage applies to market,stop-market,MIT and is bounded by nextbar high/low;Highfill uses secondaryseries with same pricebasis'),dict(url='https://docs.ninjatrader.com/ninjascript/slippage',finding='Per-execution tick property,not independently proven realizedcost'),dict(url='https://docs.ninjatrader.com/ninjascript/orderfillresolution',finding='Highresolution uses secondary pricebars')],installed_bridge=dict(path=str(addon),sha256=file_hash(addon),setting_assignment_and_readback_present=True),pairs=pairs,bollinger=figures,
        diagnosis='Observed identical2/4tickfills are consistent with documented high/low clipping on1tick Lastbars (singleprice range). Settings were assigned and readback;do not claim a measured4tick executionstress or an established bug. Direct engine-internal clipping branch not instrumented.',
        cost_channels=dict(native='Saved enginefilltuples;0incremental difference in these pairs',commission='External$5/$10roundtrip arithmetic;enginecommission disabled',sensitivity='Additional2/4ticks EACHfill on savedtrades;arithmetic counterfactual,no path/orderchange or realcost estimate',future_execution_experiment='Different mechanism must changefills/delay/quoteexecution causally;fixedexit repricing is not a complete alternative strategyPnl'),
        precise_clock_limit='Old Bollinger52trade JSON retains seconds only. Prior separate Oct6 diagnostic proved fractions for4trades;does not recover other48. No rerun to fabricate historical precision.',
        exposure_scope='First4eligible flat-position entries/day,not unrestricted all-day indicator edge. Cap reached all13Bollinger days;OFI likewise4/day. Count-limited early-day policy is part of hypothesis;no capchange.',
        risk_scope='-$900 realized-after-$10/trade gate blocks subsequent entries only;not hard daily/account loss cap. Open losses,finaltrade overshoot and gaps can exceed it. $300 research preentry estimate retained;no account-equity compliance assertion.',
        diagnostic_decision='No additionalnative diagnostic justified now: existingmatchedledgers,settingsreadback,precisiondiagnostic andofficialdocs answer cost-path question. Currentdiagnosticbudget0.',
        resume='A future execution diagnostic needs explicit causalquestion,changedfillmechanism,expectedobservation,budget before running;no samewindow performance retest.')
    atomic(target,report)
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text());done={}
    for path,state,r in allrows:
        r.setdefault('assessment_history',[]).append(dict(at=time.time(),assessment=dict(r['assessment']),reason='Documented costpath and entry-cap scope review'))
        r['assessment'].update(cost_path_review='research/bollinger-cost-path-review.json',native_slippage_response_observed=False,nominal_cost_pair_is_fee_sensitivity=True,entry_policy_scope='First4eligible flat-position trades/day under fixed time/risk filters;not all-day indicatorperformance',risk_limit_scope='Realized loss entryhalt,not hard accountloss cap',campaign_selection_scope='Allhistoricalobserved dates are development;strategy replacement on same dates is modelselection')
        if path.parent.name=='bollinger-return':r['assessment'].update(worst_day_review=next(f for f in figures if f['run_id']==r['run_id']),next_action='Freeze candidate/rules/costs/risk anddecisiondate for untouched future sample;no more same-date selection. Keep cost/concentration and missingaccountpath limitations.')
        publish(r,q,config);done[str(path)]=state
    for path,state in done.items():atomic(Path(path),state)
    atomic(ROOT/'research/bollinger-return-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','assessment_history','ack')} for r in bb])
    report['metadata_acks']=len(allrows);atomic(target,report)
    print(json.dumps(dict(pairs=len(pairs),metadata_acks=len(allrows),native_runs=0,latest_entries={p['folder']:p['latest_entry_et'] for p in pairs},bollinger=figures)),flush=True)

if __name__=='__main__':main()
