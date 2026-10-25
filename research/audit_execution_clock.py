"""Audit raw simulated clock evidence without querying order/account endpoints."""
import json
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from runner.core import ROOT,atomic,file_hash

def main():
    state=json.loads((ROOT/'data/runner/execution-clock/state.json').read_text());r=next(iter(state['experiments'].values()));doc=r['doc']
    old=json.loads((ROOT/'data/runner/bollinger-return/state.json').read_text());base=next(x for x in old['experiments'].values() if x['request']['slippageTicks']==2)
    original=[t for t in base['doc']['trades'] if t['entryTime'].startswith('2026-10-06')]
    keys=('entryTime','exitTime','entryPrice','exitPrice','side','qty','pnl')
    assert [[t[k] for k in keys] for t in original]==[[t[k] for k in keys] for t in doc['trades']]
    source=ROOT/'data/incoming/replay/2026/NQ-2026_L1/20261006.parquet';parts={0:[],1:[],2:[]}
    for b in pq.ParquetFile(source).iter_batches(batch_size=500000,columns=['Timestamp','MarketDataType','Price','Volume']):
        ts=b.column(0).cast('int64').to_numpy();k=b.column(1).to_numpy();price=b.column(2).to_numpy();size=b.column(3).to_numpy()
        for side in parts:
            keep=k==side;parts[side].append((ts[keep],price[keep],size[keep]))
    arrays={s:tuple(np.concatenate([x[i] for x in p]) for i in range(3)) for s,p in parts.items()}
    def utc_ns(ticks):return (int(ticks)-621355968000000000)*100-9*3600*10**9
    submissions=[];execs=[];trade_times=[]
    for line in doc['output']:
        p=line.split('|')
        if p[0]=='CLOCK_SUBMIT':submissions.append(dict(local=p[1],ticks=int(p[2]),utc_ns=utc_ns(p[2]),side=p[3],close=float(p[4])))
        if p[0]=='CLOCK_TRADE':trade_times.append(dict(entry=p[1],entry_ticks=int(p[2]),exit=p[3],exit_ticks=int(p[4])))
        if p[0]!='CLOCK_EXEC':continue
        target=utc_ns(p[2]);row=dict(execution_local=p[1],execution_ticks=int(p[2]),callback_local=p[3],callback_ticks=int(p[4]),primary_bar_local=p[5],name=p[6],price=float(p[7]),qty=int(p[8]),state=p[9],utc_ns=target)
        assert row['state']=='Historical' and row['execution_ticks']==row['callback_ticks']
        ts,prices,sizes=arrays[2];lo=np.searchsorted(ts,target,'left');hi=np.searchsorted(ts,target,'right')
        row['exact_timestamp_last_prices']=list(map(float,prices[lo:hi]));row['fill_price_matches_exact_last']=bool(np.any(prices[lo:hi]==row['price']))
        row['nearest_last_timestamp_distance_ns']=min(abs(target-int(ts[max(0,lo-1)])),abs(target-int(ts[min(len(ts)-1,lo)])))
        book={};same={}
        for side,label in ((0,'ask'),(1,'bid')):
            ts,prices,sizes=arrays[side];i=np.searchsorted(ts,target,'left')-1;assert i>=0
            book[label]=dict(timestamp_ns=int(ts[i]),age_ns=target-int(ts[i]),price=float(prices[i]),size=int(sizes[i]))
            same[label]=int(np.searchsorted(ts,target,'right')-np.searchsorted(ts,target,'left'))
        row['strict_prior_book']=book;row['same_timestamp_quote_events']=same
        row['book_usable']=bool(0<book['ask']['price']-book['bid']['price'] and max(v['age_ns'] for v in book.values())<=10**9 and min(v['size'] for v in book.values())>=1)
        row['spread_ticks']=(book['ask']['price']-book['bid']['price'])/.25
        execs.append(row)
    assert len(execs)==8 and len(submissions)==len(trade_times)==4
    pairs=[]
    for i,(s,t) in enumerate(zip(submissions,trade_times)):
        en,ex=execs[2*i:2*i+2];assert en['execution_ticks']==t['entry_ticks'] and ex['execution_ticks']==t['exit_ticks']
        delay=(en['utc_ns']-s['utc_ns'])/10**6;assert delay>=0
        row=dict(signal=s,entry=en,exit=ex,simulated_signal_to_execution_ms=delay)
        last=arrays[2][0];j=np.searchsorted(last,s['utc_ns'],'left')
        row['first_last_tick_after_signal_ns']=int(last[j]);row['entry_is_first_last_tick_after_signal']=en['utc_ns']==int(last[j])
        if en['book_usable'] and ex['book_usable']:
            long=s['side']=='L';entry=en['strict_prior_book']['ask' if long else 'bid']['price'];exit=ex['strict_prior_book']['bid' if long else 'ask']['price']
            row.update(diagnostic_entry_touch=entry,diagnostic_exit_touch=exit,diagnostic_touch_net_after5fee=(exit-entry)*20*(1 if long else -1)-5)
        pairs.append(row)
    costs=[]
    for name,netbase,netstress,n in [('OFI_all13days',1305,1045,52),('Bollinger_all13days',1455,1195,52)]:
        costs.append(dict(candidate=name,unique_trades=n,after5fee_net=netbase,after10fee_net=netstress,additional_adverse_ticks_per_fill_break_even_base=netbase/(2*5*n),additional_adverse_ticks_per_fill_break_even_high_fee=netstress/(2*5*n),assumption='1NQ,$5/tick,2fills/trade; incremental total adverse cost beyond recorded fills, not extra spread plus the same slippage again.'))
    sourcefiles=[Path.home()/'Documents/NinjaTrader 8/bin/Custom/AddOns'/n for n in ('NT8Bridge.cs','NT8Bridge.Backtest.cs')]
    report=dict(diagnostic_native_runs=1,diagnostic_unique_market_observations_added=0,baseline_trade_match=True,raw_execution_count=8,fractional_execution_count=sum(x['execution_ticks']%10000000!=0 for x in execs),raw_trade_execution_time_match=True,
        installed_source_hashes=[dict(path=str(p),sha256=file_hash(p)) for p in sourcefiles],quote_source_sha256=file_hash(source),pairs=pairs,cost_break_even=costs,
        finding='Tm serializer discards fractional seconds. In this HighTick1 diagnostic all8 raw simulated executions and Trade.Entry/Exit times retain fractions and match callbacks. This establishes available historical simulation precision, not live latency or real fills.',
        limitations='No exact-time precision recovery for old saved JSON. Same-timestamp L1 events have no proven execution-versus-quote interleaving. Strictly prior touch is a diagnostic and can differ from executable book. Repriced entry would alter stop/exit path; unchanged exit-time repricing is not alternate strategy PnL. Backtest clock timing is not measured routing latency. Do not generalize one day to every historical fill mode.')
    atomic(ROOT/'research/execution-clock-audit.json',report)
    print(json.dumps(dict(fractional_executions=report['fractional_execution_count'],baseline_trade_match=True,delays_ms=[p['simulated_signal_to_execution_ms'] for p in pairs],first_tick_entries=[p['entry_is_first_last_tick_after_signal'] for p in pairs],exact_last_price_matches=[x['fill_price_matches_exact_last'] for x in execs],cost_break_even=costs),indent=2))

if __name__=='__main__':main()
