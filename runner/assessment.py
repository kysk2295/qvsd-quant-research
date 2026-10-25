"""Evidence-based assessment, separate from immutable calculation lifecycle status."""
from datetime import datetime
from zoneinfo import ZoneInfo

def additional_slippage_evidence(trades,fee,ticks_per_fill):
    """Arithmetic sensitivity beyond observed native fills, not a new execution simulation."""
    adjusted=[dict(t,pnl=t['pnl']-2*5*ticks_per_fill*t['qty']) for t in trades]
    pnl=[t['pnl']-fee*t['qty'] for t in adjusted]
    return dict(additional_ticks_per_fill=ticks_per_fill,nq_tick_value=5,assumed_fills_per_roundtrip=2,
                net=sum(pnl),ledger_evidence=ledger_evidence(adjusted,fee),
                basis='Additional adverse cost beyond native observed fills; arithmetic sensitivity only, no changed orders or fills; not an estimate of actual live slippage')

def ledger_evidence(trades,fee):
    pnl=[t['pnl']-fee*t['qty'] for t in trades]
    ranked=sorted((p for p in pnl if p>0),reverse=True)
    daily={}
    for t,p in zip(trades,pnl):
        stamp=datetime.fromisoformat(t['exitTime'])
        if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=ZoneInfo('Asia/Seoul'))
        day=stamp.astimezone(ZoneInfo('America/New_York')).date().isoformat()
        daily[day]=daily.get(day,0)+p
    return dict(net_without_best_positive=sum(pnl)-sum(ranked[:1]),
                net_without_best_three_positive=sum(pnl)-sum(ranked[:3]),
                top_three_positive=sum(ranked[:3]),daily_net=daily,
                active_days=len(daily),daily_basis='exit date ET; zero-trade days require session audit',
                extra_round_trip_fee_5_net=sum(pnl)-5*sum(t['qty'] for t in trades),
                unrealized_drawdown=None,unrealized_risk_note='Not reconstructible from closed trade ledger; requires path/equity evidence')
def assess(trades,fee,minimum_trades,implementation_error=None,data_issue=None,signals=None,condition_rejected=None):
    pnl=[t['pnl']-fee*t['qty'] for t in trades]
    net=sum(pnl);gains=sum(p for p in pnl if p>0)
    concentration=dict(largest_positive_share_of_gross_profit=max(pnl)/gains if gains else None,
                       largest_trade_share_of_net_profit=max(pnl)/net if pnl and net>0 else None,
                       basis='net trade pnl after assumed per-contract round-trip fee',observed_trades=len(pnl))
    if implementation_error:decision,reason='execution_error',implementation_error
    elif data_issue:decision,reason='deferred',data_issue
    elif not pnl:decision,reason='condition_mismatch' if signals and condition_rejected else 'deferred','No trades; insufficient evidence of strategy performance'
    elif net<=0:decision,reason='performance_fail','Negative after-cost result in this finite sample; not proof of permanent failure'
    elif len(pnl)<minimum_trades:decision,reason='deferred','Positive result but fewer trades than the pre-registered sample threshold'
    else:decision,reason='further_validation','Positive sample; other gates and prospective/Replay validation still required'
    return dict(version=1,decision=decision,reason=reason,net_after_assumed_fee=net,trade_count=len(pnl),
                minimum_trades=minimum_trades,concentration=concentration,
                permanent_discard=False,independent_oos=False,strategy_replay_validated=False,
                next_action='extend data without retuning these parameters' if decision=='deferred' else 'review hypothesis and costs; retain full evidence')
