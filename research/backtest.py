"""Exploratory 5-minute proxy test. No live orders. Python standard library only."""
import json, math, csv, hashlib, statistics
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
ROOT=Path(__file__).resolve().parent
NY=ZoneInfo('America/New_York')
SPECS={'NQ':{'tick':.25,'point':2.0},'GC':{'tick':.1,'point':10.0}}

def load(symbol):
    path=ROOT/'data'/f'{symbol}_5m.json'
    raw=path.read_bytes(); d=json.loads(raw)['chart']['result'][0]
    q=d['indicators']['quote'][0]; bars=[]; invalid=0
    for i,t in enumerate(d['timestamp']):
        vals=[q[k][i] for k in ('open','high','low','close','volume')]
        if any(v is None or not math.isfinite(v) for v in vals):
            invalid+=1;continue
        o,h,l,c,v=vals
        tick=SPECS[symbol]["tick"]
        o,h,l,c=(round(round(x/tick)*tick,8) for x in (o,h,l,c))
        if not(l<=min(o,c)<=max(o,c)<=h) or v<0: raise ValueError('Invalid OHLCV')
        dt=datetime.fromtimestamp(t,timezone.utc).astimezone(NY)
        bars.append(dict(t=t,dt=dt,date=str(dt.date()),minute=dt.hour*60+dt.minute,o=o,h=h,l=l,c=c,v=v))
    if any(bars[i]['t']<=bars[i-1]['t'] for i in range(1,len(bars))):raise ValueError('Timestamps not unique/sorted')
    # ATR proxy is rolling mean of 14 true ranges, not Wilder smoothing.
    tr=[]
    for i,b in enumerate(bars):
        prev=bars[i-1]['c'] if i else b['o']
        tr.append(max(b['h']-b['l'],abs(b['h']-prev),abs(b['l']-prev)))
        b['atr']=statistics.mean(tr[-14:]) if i>=13 else None
    sessions=defaultdict(list)
    for b in bars:
        if b['dt'].weekday()<5 and 570<=b['minute']<960:sessions[b['date']].append(b)
    complete={};excluded={}
    for day,bs in sessions.items():
        if [b['minute'] for b in bs]!=list(range(570,960,5)):
            excluded[day]=len(bs); continue
        complete[day]=bs
    return complete,dict(symbol=symbol,sha256=hashlib.sha256(raw).hexdigest(),raw_rows=len(d['timestamp']),null_rows=invalid,valid_rows=len(bars),first_valid=bars[0]['dt'].isoformat(),last_valid=bars[-1]['dt'].isoformat(),complete_sessions=len(complete),excluded_sessions=excluded,quote_name=d['meta'].get('shortName'),source=f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}%3DF?range=60d&interval=5m')

def exit_fill(b,side,stop,target,slip):
    # Price gaps execute at open, stops before targets if both touched.
    if side==1:
        if b['o']<=stop:return b['o']-slip,'gap_stop'
        if b['o']>=target:return target,'target'
        if b['l']<=stop:return stop-slip,'stop'
        if b['h']>=target:return target,'target'
    else:
        if b['o']>=stop:return b['o']+slip,'gap_stop'
        if b['o']<=target:return target,'target'
        if b['h']>=stop:return stop+slip,'stop'
        if b['l']<=target:return target,'target'
    return None

def run(sessions,symbol,strategy,slip_ticks=2,fee=2.5,or_minutes=15,max_contracts=10):
    tick=SPECS[symbol]['tick'];point=SPECS[symbol]['point'];slip=slip_ticks*tick
    trades=[];daily=[];equity=150000.;peak=equity;dd=0.;min_equity=equity
    for day,bs in sessions.items():
        pnl=0.;n=0;pos=None;pending=None;armed=None;pv=0.;vol=0.;history=[]
        n_range=(60 if strategy=='failed_ib' else or_minutes)//5
        hi=max(b['h'] for b in bs[:n_range]);lo=min(b['l'] for b in bs[:n_range]);mid=(hi+lo)/2
        for i,b in enumerate(bs):
            # The last bar opens 15:55. Liquidate at that open, not an unknown close.
            if pending and pos is None and b['minute']<900:
                side,stop,target_hint=pending;entry=b['o']+side*slip
                distance=side*(entry-stop)
                if distance>=2*tick:
                    target=entry+side*2*distance if target_hint is None else target_hint
                    target=round(round(target/tick)*tick,8)
                    reward=side*(target-entry)
                    qty=min(max_contracts,math.floor(300/(distance*point+slip*point+fee)))
                    if qty>0 and reward>=distance:
                        pos=dict(side=side,entry=entry,stop=stop,target=target,qty=qty,entry_time=b['dt'].isoformat(),start_i=i)
                        n+=1
                pending=None
            if pos:
                p=pos
                fill=(b['o']-p['side']*slip,'time') if b['minute']>=955 else exit_fill(b,p['side'],p['stop'],p['target'],slip)
                # Conservative bar-based adverse equity bound with stop execution model.
                adverse=b['l'] if p['side']==1 else b['h']
                if fill and fill[1] in ('stop','gap_stop','time'): adverse=fill[0]
                elif fill and fill[1]=='target' and ((p['side']==1 and b['o']>=p['target']) or (p['side']==-1 and b['o']<=p['target'])): adverse=fill[0]
                adverse_equity=equity+(adverse-p['entry'])*p['side']*point*p['qty']-fee*p['qty']
                min_equity=min(min_equity,adverse_equity);dd=max(dd,peak-adverse_equity)
                if fill:
                    px,reason=fill;net=(px-p['entry'])*p['side']*point*p['qty']-fee*p['qty']
                    trades.append(dict(symbol=symbol,strategy=strategy,date=day,exit_time=b['dt'].isoformat(),exit=px,reason=reason,pnl=net,**p))
                    pnl+=net;equity+=net;peak=max(peak,equity);pos=None
                else:
                    mark=equity+(b['c']-p['entry'])*p['side']*point*p['qty']-fee*p['qty']
                    peak=max(peak,mark)
            pv+=(b['h']+b['l']+b['c'])/3*b['v'];vol+=b['v'];vwap=pv/vol if vol else b['c']
            history.append(vwap)
            if pos or i<n_range or b['minute']>=895 or n>=4 or pnl<=-900 or equity<=145500 or b['atr'] is None:continue
            prev=bs[i-1];buffer=max(tick,.05*b['atr'])
            long_filter=b['c']>vwap and i>=3 and vwap>history[i-3]
            short_filter=b['c']<vwap and i>=3 and vwap<history[i-3]
            signal=None
            if strategy=='breakout':
                if prev['c']<=hi and b['c']>hi+buffer and long_filter: signal=(1,b['c']-max(1.5*b['atr'],.25*(hi-lo)),None)
                elif prev['c']>=lo and b['c']<lo-buffer and short_filter: signal=(-1,b['c']+max(1.5*b['atr'],.25*(hi-lo)),None)
            elif strategy=='retest':
                if armed and i-armed[1]>6:armed=None
                if armed and i>armed[1]:
                    side=armed[0]
                    if side==1 and b['l']<=hi+buffer and b['c']>hi+buffer and long_filter:
                        signal=(1,min(b['l'],hi)-buffer,None);armed=None
                    elif side==-1 and b['h']>=lo-buffer and b['c']<lo-buffer and short_filter:
                        signal=(-1,max(b['h'],lo)+buffer,None);armed=None
                    elif (side==1 and b['c']<mid) or (side==-1 and b['c']>mid):armed=None
                if not armed and not signal:
                    if prev['c']<=hi and b['c']>hi+buffer and long_filter:armed=(1,i)
                    elif prev['c']>=lo and b['c']<lo-buffer and short_filter:armed=(-1,i)
            else:
                if b['h']>hi+buffer and mid<b['c']<hi:signal=(-1,b['h']+buffer,mid)
                elif b['l']<lo-buffer and lo<b['c']<mid:signal=(1,b['l']-buffer,mid)
            if signal:
                side,stop,target=signal
                # Protective levels must lie on exchange tick grid.
                stop=(math.floor(stop/tick) if side==1 else math.ceil(stop/tick))*tick
                if target is not None:target=round(target/tick)*tick
                pending=(side,stop,target)
        assert pos is None,'End-of-session position leak'
        daily.append(dict(date=day,pnl=pnl,entries=n,equity=equity))
    return trades,daily,dict(bar_adverse_drawdown=dd,min_model_equity=min_equity)

def metrics(trades,daily):
    gains=sum(t['pnl'] for t in trades if t['pnl']>0);loss=-sum(t['pnl'] for t in trades if t['pnl']<0)
    eq=150000.;peak=eq;dd=0
    for t in trades:eq+=t['pnl'];peak=max(peak,eq);dd=max(dd,peak-eq)
    return dict(trades=len(trades),net=round(eq-150000,2),return_pct=round((eq/150000-1)*100,3),profit_factor=round(gains/loss,3) if loss else None,win_pct=round(100*sum(t['pnl']>0 for t in trades)/len(trades),1) if trades else 0,closed_trade_mdd=round(dd,2),days=len(daily),days_ge4=sum(d['entries']>=4 for d in daily),zero_days=sum(d['entries']==0 for d in daily))

def main():
    out=[];audits=[];regimes=[]
    for symbol in SPECS:
        sessions,audit=load(symbol);audits.append(audit);days=list(sessions);cut=days[-15]
        for day,bs in sessions.items():
            regimes.append(dict(symbol=symbol,date=day,open=bs[0]['o'],close=bs[-1]['c'],range=max(b['h'] for b in bs)-min(b['l'] for b in bs),abs_net=abs(bs[-1]['c']-bs[0]['o']),efficiency=abs(bs[-1]['c']-bs[0]['o'])/sum(abs(b['c']-(bs[i-1]['c'] if i else b['o'])) for i,b in enumerate(bs))))
        for strategy in ['breakout','retest','failed_ib']:
            for label,slippage,fee in [('base',2,2.5),('stress',4,5.)]:
                ts,ds,extra=run(sessions,symbol,strategy,slippage,fee)
                recent_ts,recent_ds,_=run({d:b for d,b in sessions.items() if d>=cut},symbol,strategy,slippage,fee)
                out.append(dict(symbol=symbol,strategy=strategy,cost=label,cutoff=cut,full=metrics(ts,ds),earlier=metrics([t for t in ts if t['date']<cut],[d for d in ds if d['date']<cut]),recent=metrics(recent_ts,recent_ds),recent_continuous_account=metrics([t for t in ts if t['date']>=cut],[d for d in ds if d['date']>=cut]),**extra))
                for name,rows in [('trades',ts),('daily',ds)]:
                    if rows:
                        with (ROOT/f'{symbol}_{strategy}_{label}_{name}.csv').open('w') as f:
                            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (ROOT/'results.json').write_text(json.dumps(out,indent=2))
    (ROOT/'data_audit.json').write_text(json.dumps(audits,indent=2))
    with (ROOT/'regimes.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(regimes[0]));w.writeheader();w.writerows(regimes)
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
