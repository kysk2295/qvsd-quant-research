"""Strictly preceding L1 touch repricing of fixed native trade timestamps."""
import json
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pyarrow.parquet as pq
from runner.core import ROOT,atomic,file_hash

def main():
    grouped=defaultdict(list)
    for segment in ('early','late'):
        state=json.loads((ROOT/f'data/runner/ofi-{segment}/state.json').read_text())
        r=next(r for r in state['experiments'].values() if r['request']['slippageTicks']==2)
        for t in r['doc']['trades']:
            et=datetime.fromisoformat(t['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
            grouped[et.date().isoformat()].append(t)
    evidence=[];hashes=[]
    for day,trades in grouped.items():
        path=ROOT/f'data/incoming/replay/2026/NQ-2026_L1/{day.replace("-", "")}.parquet'
        sides={0:[],1:[]}
        for b in pq.ParquetFile(path).iter_batches(batch_size=500000,columns=['Timestamp','MarketDataType','Price','Volume']):
            ts=b.column(0).cast('int64').to_numpy();kind=b.column(1).to_numpy();p=b.column(2).to_numpy();v=b.column(3).to_numpy()
            for side in (0,1):
                mask=kind==side;sides[side].append((ts[mask],p[mask],v[mask]))
        arrays={s:tuple(np.concatenate([x[i] for x in parts]) for i in range(3)) for s,parts in sides.items()}
        def quote(target):
            book={}
            for s,(ts,p,v) in arrays.items():
                i=np.searchsorted(ts,target,side='left')-1
                if i<0 or target-int(ts[i])>10**9 or v[i]<1:return None
                book[s]=dict(timestamp_ns=int(ts[i]),price=float(p[i]),size=int(v[i]),age_ns=target-int(ts[i]))
            if book[0]['price']<=book[1]['price']:return None
            return book
        for t in trades:
            row=dict(date=day,trade=t,scenarios=[])
            for ms in (0,100,1000):
                targets=[int(datetime.fromisoformat(t[k]).replace(tzinfo=ZoneInfo('Asia/Seoul')).timestamp()*10**9)+ms*10**6 for k in ('entryTime','exitTime')]
                a,b=map(quote,targets);scenario=dict(delay_ms=ms,entry_book=a,exit_book=b,available=a is not None and b is not None)
                if a is not None and b is not None:
                    long=t['side']=='Long';entry=a[0 if long else 1]['price'];exit=b[1 if long else 0]['price']
                    scenario.update(entry_touch=entry,exit_touch=exit,net_after5fee=(exit-entry)*(1 if long else -1)*20-5,
                        entry_spread_ticks=(a[0]['price']-a[1]['price'])/.25,exit_spread_ticks=(b[0]['price']-b[1]['price'])/.25)
                row['scenarios'].append(scenario)
            evidence.append(row)
        hashes.append(dict(date=day,sha256=file_hash(path)))
        print(day,'audited',len(trades),'unique trades',flush=True)
    assert len(evidence)==48
    summary=[]
    for ms in (0,100,1000):
        selected=[(r,next(s for s in r['scenarios'] if s['delay_ms']==ms)) for r in evidence]
        valid=[(r,s) for r,s in selected if s['available']];daily=defaultdict(float)
        for r,s in valid:daily[r['date']]+=s['net_after5fee']
        summary.append(dict(delay_ms=ms,available=len(valid),missing=48-len(valid),net_after5fee=sum(daily.values()),daily=dict(daily),net_without_best_day=sum(daily.values())-max(daily.values()) if daily else None,max_spread_ticks=max([max(s['entry_spread_ticks'],s['exit_spread_ticks']) for _,s in valid],default=None)))
    output=dict(unique_trades=48,source_hashes=hashes,scenarios=summary,evidence=evidence,
        caveat='Diagnostic touch repricing of fixed original exit times; not a valid alternate strategy backtest. Orders, stops and exits could change under altered fills. Same-timestamp quote groups excluded, but native timestamp precision may be coarser than quote timestamps. Queue position, cancellations, routing latency and price impact unknown. Displayed size is not guaranteed liquidity. No additional full spread subtraction.')
    atomic(ROOT/'research/ofi-touch-cost-audit.json',output);print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
