"""Decode only registered missing context dates; no strategy outcomes."""
import sys,json,time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pyarrow.parquet as pq
from runner.core import ROOT,atomic,file_hash
sys.path.insert(0,r'C:\Users\User\Documents\Codex\2026-10-04\dlrj\work\nt8-mcp\server')
from nt8_mcp.nrd_offline import convert_file,build_table

def main():
    plan=json.loads((ROOT/'research/nr7-history-chunk1-plan.json').read_text());resultpath=ROOT/'research/nr7-history-chunk1-decoded.json'
    reports=json.loads(resultpath.read_text()) if resultpath.exists() else []
    requested=sys.argv[1:] or plan['dates'];assert set(requested)<=set(plan['dates'])
    for day in requested:
        assert not any(r['date']==day for r in reports),'Date already decoded;no repeat'
        source=Path.home()/f'Documents/NinjaTrader 8/db/replay/NQ 12-26/{day.replace("-", "")}.nrd';p=ROOT/f'data/incoming/replay/2026/NQ-2026_L1/{day.replace("-", "")}.parquet'
        assert source.exists() and not p.exists()
        d=convert_file(source,want_l1=True,want_l2=False,salvage=False);assert d.get('integrity_ok',True) and not d.get('truncated');table=build_table(d['L1'],source);assert table.num_rows
        tmp=p.with_suffix('.pending');pq.write_table(table,tmp,compression='zstd');tmp.replace(p)
        ts=table.column('Timestamp').cast('int64').to_numpy();kind=table.column('MarketDataType').to_numpy();price=table.column('Price').to_numpy();size=table.column('Volume').to_numpy();assert np.all(np.diff(ts)>=0)
        opening=int(datetime.fromisoformat(day+'T09:30').replace(tzinfo=ZoneInfo('America/New_York')).timestamp())*10**9
        keep=(kind==2)&(ts>=opening)&(ts<opening+390*60*10**9);t=ts[keep];prices=price[keep];sizes=size[keep]
        assert len(t)>0 and np.all(sizes>0) and np.all(prices>0) and np.all(prices*4==np.rint(prices*4))
        minutes=(t-opening)//(60*10**9);starts=np.flatnonzero(np.r_[True,minutes[1:]!=minutes[:-1]]);ends=np.r_[starts[1:]-1,len(t)-1];assert list(minutes[starts])==list(range(390))
        bars=[dict(minute=570+int(minutes[a]),open=float(prices[a]),high=float(prices[a:b+1].max()),low=float(prices[a:b+1].min()),close=float(prices[b]),volume=int(sizes[a:b+1].sum())) for a,b in zip(starts,ends)]
        report=dict(date=day,source=str(source),nrd_sha256=file_hash(source),parquet_sha256=file_hash(p),rows=table.num_rows,integrity_passed=True,truncated=False,rth_minutes=390,rth_ticks=len(t),high=float(prices.max()),low=float(prices.min()),close=float(prices[-1]),bars=bars,role='historical_RTH_context_only',native_performance_runs=0)
        reports.append(report);atomic(ROOT/'research/nr7-history-chunk1-decoded.json',reports);print(json.dumps({k:report[k] for k in ('date','integrity_passed','rth_minutes','rth_ticks')}),flush=True)
        del d,table,ts,kind,price,size,prices,sizes,t,bars
    print(f'{len(reports)}registered dates decoded and checked;no outcome computed',flush=True)

if __name__=='__main__':main()
