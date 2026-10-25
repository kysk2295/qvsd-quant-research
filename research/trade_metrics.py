"""Descriptive, after-cost ledger metrics; no strategy or price-feed execution."""
import math
import statistics as st
from collections import Counter,defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

def mean(values):return st.mean(values) if values else None
def ratio(a,b):return a/b if b else None
def local(stamp):
    value=datetime.fromisoformat(stamp)
    if value.tzinfo is None:value=value.replace(tzinfo=ZoneInfo('Asia/Seoul'))
    return value.astimezone(ZoneInfo('America/New_York'))

def drawdown(values):
    equity=peak=worst=0.;under=longest=0
    for value in values:
        equity+=value;peak=max(peak,equity);worst=max(worst,peak-equity)
        under=under+1 if equity<peak else 0;longest=max(longest,under)
    return dict(maximum=worst,longest_underwater_observations=longest,unrecovered_at_end=equity<peak)

def bootstrap_days(values):
    if len(values)<10:return dict(interval=None,reason='Fewer than10sessions; no resampling interval reported')
    import numpy as np
    rng=np.random.default_rng(20261025);a=np.asarray(values);n=len(a);length=3
    starts=rng.integers(0,n,size=(2000,math.ceil(n/length)))
    indexes=((starts[:,:,None]+np.arange(length))%n).reshape(2000,-1)[:,:n]
    interval=np.quantile(a[indexes].mean(axis=1),[.025,.975]).tolist()
    return dict(mean_daily_pnl_interval=interval,method='circular moving session blocks',block_sessions=3,resamples=2000,seed=20261025,
        limitation='Exploratory short-sample resampling sensitivity only; stationarity and block length unvalidated; no multiple-selection correction or proof of edge')

def evaluate(trades,dates,fee,initial_stop_ticks=None):
    dates=sorted(set(dates));daily={d:0. for d in dates};counts=Counter();nets=[];holds=[];seen=set();exc=[]
    entries=defaultdict(list);sides=defaultdict(list);exits=Counter();winrun=lossrun=maxwin=maxloss=0
    ordered=sorted(trades,key=lambda t:(local(t['exitTime']),local(t['entryTime'])))
    for t in ordered:
        key=tuple(t[k] for k in ('entryTime','exitTime','side','entryPrice','exitPrice','qty'))
        if key in seen:raise ValueError('Duplicate roundtrip within cost case')
        seen.add(key);en,ex=local(t['entryTime']),local(t['exitTime']);qty=t['qty']
        if ex<en or qty<=0 or en.date()!=ex.date():raise ValueError('Invalid or overnight trade for this intraday review')
        day=ex.date().isoformat()
        if day not in daily:raise ValueError('Trade outside audited sessions')
        side=1 if t['side']=='Long' else -1 if t['side']=='Short' else 0
        gross=(t['exitPrice']-t['entryPrice'])*side*20*qty
        if side==0 or not math.isfinite(gross) or abs(gross-t['pnl'])>1e-6:raise ValueError('NQ fill/PnL mismatch')
        net=gross-fee*qty;nets.append(net);daily[day]+=net;counts[day]+=1;holds.append((ex-en).total_seconds())
        entries[f'{en.hour:02d}:00'].append(net);sides[t['side']].append(net);exits[t.get('exitName','unknown')]+=1
        winrun=winrun+1 if net>0 else 0;lossrun=lossrun+1 if net<0 else 0;maxwin=max(maxwin,winrun);maxloss=max(maxloss,lossrun)
        if all(isinstance(t.get(k),(int,float)) and math.isfinite(t[k]) and t[k]>=0 for k in ('mae','mfe')):
            mae,mfe=t['mae']*20*qty,t['mfe']*20*qty
            exc.append(dict(mae=mae,mfe=mfe,gross=gross,etd=mfe-gross,net=net,
                consistent=mfe+1e-6>=max(0,gross) and mae+1e-6>=max(0,-gross)))
    wins=[x for x in nets if x>0];losses=[-x for x in nets if x<0];n=len(nets);net=sum(nets)
    avgwin,avgloss=mean(wins),mean(losses);payoff=ratio(avgwin,avgloss) if avgwin is not None and avgloss is not None else None
    dailyvalues=list(daily.values());dd=drawdown(nets);dailyd=drawdown(dailyvalues)
    # Fixed starting-capital normalized daily PnL, not compounded account return.
    dailyreturns=[x/150000 for x in dailyvalues];sd=st.stdev(dailyreturns) if len(dailyreturns)>1 else 0
    downside=math.sqrt(mean([min(x,0)**2 for x in dailyreturns])) if dailyreturns else 0
    positives=sorted((x for x in dailyvalues if x>0),reverse=True)
    valid=[x for x in exc if x['consistent']];ranges=[x for x in valid if x['mae']+x['mfe']>0]
    # Direction-adjusted range efficiencies. Descriptive bar-based diagnostics, not signal skill.
    entryeff=mean([x['mfe']/(x['mae']+x['mfe']) for x in ranges])
    exiteff=mean([(x['gross']+x['mae'])/(x['mae']+x['mfe']) for x in ranges])
    totalqty=sum(t['qty'] for t in ordered)
    result=dict(trades=n,sessions=len(dates),wins=len(wins),losses=len(losses),breakeven=n-len(wins)-len(losses),net=net,
        win_rate=ratio(len(wins),n),avg_win=avgwin,avg_loss_abs=avgloss,realized_payoff_ratio=payoff,
        breakeven_win_rate_among_nonzero=1/(1+payoff) if payoff is not None else None,
        expectancy_per_trade=ratio(net,n),median_trade=st.median(nets) if nets else None,
        profit_factor=ratio(sum(wins),sum(losses)),profit_factor_note='undefined when no losing trades; no infinity ranking',
        largest_win=max(wins) if wins else None,largest_loss=-max(losses) if losses else None,
        max_consecutive_wins=maxwin,max_consecutive_losses=maxloss,closed_trade_drawdown=dd,
        closed_daily_drawdown=dailyd,net_over_closed_dd=ratio(net,dd['maximum']),
        active_sessions=sum(c>0 for c in counts.values()),trades_per_session=ratio(n,len(dates)),
        fraction_sessions_with_four_or_more_filled_roundtrips=ratio(sum(counts[d]>=4 for d in dates),len(dates)),
        frequency_note='Daily diagnostic, not competition round compliance; counts filled roundtrips, not order submissions',
        daily=daily,positive_days=sum(x>0 for x in dailyvalues),worst_day=min(dailyvalues) if dailyvalues else None,
        mean_daily_pnl=mean(dailyvalues),median_daily_pnl=st.median(dailyvalues) if dailyvalues else None,
        empirical_worst_decile_mean=mean(sorted(dailyvalues)[:max(1,math.ceil(.1*len(dates)))]) if dates else None,
        tail_note='Observed bottom ceil(10%*sessions), often1–2days; not estimated future CVaR',
        net_without_best_positive_day=net-(positives[0] if positives else 0),net_without_best_three_positive_days=net-sum(positives[:3]),
        best_positive_day_share_of_positive_day_profits=ratio(positives[0],sum(positives)) if positives else None,
        mean_holding_seconds=mean(holds),median_holding_seconds=st.median(holds) if holds else None,
        duration_note='Native ledger clock precision only; seconds-only zero duration does not prove instantaneous execution',
        daily_sharpe_unannualized=ratio(mean(dailyreturns),sd) if dailyreturns else None,
        daily_sortino_unannualized_mar0=ratio(mean(dailyreturns),downside) if dailyreturns else None,
        risk_adjusted_note='Descriptive short sample; zero rf/MAR; normalized by fixed150000. Not native monthly Sharpe/Sortino, no annualization or statistical significance.',
        additional_ticks_per_fill_breakeven=ratio(net,2*5*totalqty) if net>0 else 0 if n else None,
        additional_cost_sensitivity=[dict(ticks_per_fill=k,net=net-k*2*5*totalqty) for k in (0,1,2,4)],
        cost_note='Extra adverse cost on fixed observed fills, not a new fill-path simulation;2fills/roundtrip;native nominal slippage is not added twice',
        entry_hour={k:dict(trades=len(v),net=sum(v),expectancy=mean(v)) for k,v in entries.items()},
        side={k:dict(trades=len(v),net=sum(v),expectancy=mean(v)) for k,v in sides.items()},exit_names=dict(exits),
        excursion=dict(observed=len(exc),consistent=len(valid),inconsistent=len(exc)-len(valid),mean_mae_currency=mean([x['mae'] for x in valid]),
            mean_mfe_currency=mean([x['mfe'] for x in valid]),mean_end_trade_giveback_gross=mean([x['etd'] for x in valid]),
            mean_entry_range_efficiency=entryeff,mean_exit_range_efficiency=exiteff,
            net_capture_of_total_mfe=ratio(sum(x['net'] for x in valid),sum(x['mfe'] for x in valid)),
            losing_trades_with_positive_mfe=sum(x['net']<0 and x['mfe']>0 for x in valid),
            limitation='Native bar-based MAE/MFE; not verified tick-ordered executable opportunity. Efficiencies conditional on realized holding interval, not causal entry skill; no retrospective exit optimization.'),
        sample_uncertainty=bootstrap_days(dailyvalues),independent_oos=False)
    result['mean_net_R']=mean([x/(initial_stop_ticks*5*t['qty']) for x,t in zip(nets,ordered)]) if initial_stop_ticks and n else None
    result['R_basis']=f'Nominal initial stop{initial_stop_ticks}ticks; not maximum realized loss' if initial_stop_ticks else 'Initial strategy-specific stop absent from ledger; no invented R denominator'
    return result
