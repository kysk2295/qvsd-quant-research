"""Best-quote integrity and causal minute aggregates; no returns or trading outcomes."""
import json,struct,gc
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pyarrow.parquet as pq
from runner.core import ROOT,atomic,file_hash

NY=ZoneInfo('America/New_York');NS=10**9
def side_contribution(prices,sizes,side):
    if side==1:return (prices[1:]>=prices[:-1])*sizes[1:]-(prices[1:]<=prices[:-1])*sizes[:-1]
    if side==0:return -((prices[1:]<=prices[:-1])*sizes[1:])+(prices[1:]>=prices[:-1])*sizes[:-1]
    raise ValueError('Only Ask0/Bid1 are quote updates; Last is not OFI')

def audit_day(day):
    compact=day.replace('-','');file=ROOT/f'data/incoming/replay/2026/NQ-2026_L1/{compact}.parquet'
    nrd=Path.home()/f'Documents/NinjaTrader 8/db/replay/NQ 12-26/{compact}.nrd'
    fmt=struct.Struct('<diddddd i qq q')
    with nrd.open('rb') as stream:head=stream.read(44*80)
    slots=[fmt.unpack_from(head,i*80) for i in range(44)]
    pf=pq.ParquetFile(file);metadata=pf.schema_arrow.metadata
    assert str(pf.schema_arrow.field('Timestamp').type)=='timestamp[ns, tz=UTC]'
    assert int(metadata[b'nrd2parquet.source_size'])==nrd.stat().st_size,'NRD source size changed'
    opening=int(datetime.fromisoformat(day+'T09:30').replace(tzinfo=NY).timestamp())*NS;ending=opening+390*60*NS
    counts=np.zeros(10,dtype=np.int64);sums=np.zeros(10,dtype=np.int64);parts=[];prev=None;negative_times=0;ties=0
    for batch in pf.iter_batches(batch_size=500000,columns=['Timestamp','MarketDataType','Price','Volume']):
        ts=batch.column(0).cast('int64').to_numpy();kind=batch.column(1).to_numpy();price=batch.column(2).to_numpy();vol=batch.column(3).to_numpy()
        dt=np.diff(ts);negative_times+=int(np.sum(dt<0));ties+=int(np.sum(dt==0))
        if prev is not None:negative_times+=int(ts[0]<prev);ties+=int(ts[0]==prev)
        prev=ts[-1]
        for k in np.unique(kind):
            mask=kind==k;counts[k]+=int(mask.sum());sums[k]+=int(vol[mask].sum())
        keep=(kind<2)&(ts>=opening)&(ts<ending)
        parts.append((ts[keep].copy(),kind[keep].copy(),price[keep].copy(),vol[keep].copy()))
    mismatches=[]
    for k in range(10):
        if counts[k]!=slots[k][1] or sums[k]!=slots[k][10]:mismatches.append(dict(type=k,rows=int(counts[k]),header_rows=slots[k][1],volume=int(sums[k]),header_volume=slots[k][10]))
    ts,kind,price,vol=[np.concatenate([part[i] for part in parts]) for i in range(4)];del parts;gc.collect()
    assert len(ts)>0
    bad_price=(~np.isfinite(price))|(price<=0)|(np.abs(price*4-np.rint(price*4))>1e-8)
    bad_size=vol<=0
    # Every side update is a replacement queue price and quantity, not a size delta.
    contribution=np.zeros(len(ts),dtype=np.int64)
    for side in (0,1):
        indices=np.flatnonzero(kind==side);p=price[indices];q=vol[indices]
        values=side_contribution(p,q,side)
        contribution[indices[1:]]=values
    idx=np.arange(len(ts));askidx=np.maximum.accumulate(np.where(kind==0,idx,-1));bididx=np.maximum.accumulate(np.where(kind==1,idx,-1))
    group_end=np.flatnonzero(np.r_[ts[1:]!=ts[:-1],True]);group_start=np.r_[0,group_end[:-1]+1]
    at=askidx[group_end];bt=bididx[group_end];has=(at>=0)&(bt>=0)
    # Unknown side must never index -1 (the future final row of the day).
    safeat=np.maximum(at,0);safebt=np.maximum(bt,0)
    ask=np.where(at>=0,price[safeat],np.nan);bid=np.where(bt>=0,price[safebt],np.nan)
    aq=np.where(at>=0,vol[safeat],0);bq=np.where(bt>=0,vol[safebt],0);gt=ts[group_end]
    crossed=has&(bid>ask);locked=has&(bid==ask)
    stale=has&(((gt-ts[safeat])>NS)|((gt-ts[safebt])>NS))
    gaps=np.r_[0,np.diff(gt)]
    minutes=(gt-opening)//(60*NS)
    group_ofi=np.add.reduceat(contribution,group_start)
    output=[]
    for minute in range(390):
        lo=int(np.searchsorted(minutes,minute));hi=int(np.searchsorted(minutes,minute+1));mask=slice(lo,hi);length=hi-lo
        rawlo=np.searchsorted(ts,opening+minute*60*NS);rawhi=np.searchsorted(ts,opening+(minute+1)*60*NS)
        updates=np.bincount(kind[rawlo:rawhi],minlength=2)
        valid=bool(length and np.all(has[mask]) and not np.any(crossed[mask]|locked[mask]|stale[mask]) and not np.any(gaps[mask]>NS) and np.all(updates>0))
        last=hi-1 if length else None
        boundary=opening+(minute+1)*60*NS
        if last is not None:
            valid=valid and bool(boundary-ts[safeat[last]]<=NS and boundary-ts[safebt[last]]<=NS)
        output.append(dict(end_utc_ns=int(opening+(minute+1)*60*NS),eligible=valid,ofi=int(group_ofi[mask].sum()),
            mean_depth=float(np.mean((aq[mask]+bq[mask])/2)) if length else 0,
            group_count=length,ask_updates=int(updates[0]),bid_updates=int(updates[1]),
            crossed_groups=int(crossed[mask].sum()),locked_groups=int(locked[mask].sum()),stale_groups=int(stale[mask].sum()),
            max_group_gap_ns=int(gaps[mask].max()) if length else None,
            last_source_ns=int(gt[last]) if last is not None else None,
            end_bid=float(bid[last]) if last is not None and has[last] else None,end_ask=float(ask[last]) if last is not None and has[last] else None))
    integrity=not mismatches and negative_times==0 and not np.any(bad_price|bad_size)
    if not integrity:
        for row in output:row['eligible']=False
    report=dict(date=day,source=str(file),source_sha256=file_hash(file),nrd_sha256=file_hash(nrd),schema=str(pf.schema_arrow),
        rows=int(counts.sum()),type_counts=counts.tolist(),header_mismatches=mismatches,negative_timestamp_steps=negative_times,equal_timestamp_steps=ties,
        rth_quote_events=len(ts),bad_quote_prices=int(bad_price.sum()),nonpositive_quote_sizes=int(bad_size.sum()),
        settled_groups=len(gt),crossed_groups=int(crossed.sum()),locked_groups=int(locked.sum()),stale_groups=int(stale.sum()),
        rth_minutes_with_quotes=sum(x['group_count']>0 for x in output),eligible_minutes=sum(x['eligible'] for x in output),
        integrity_passed=integrity,record_order_only=True,exchange_sequence_available=False)
    return report,output

def audit_depth():
    file=ROOT/'data/incoming/replay/2026/NQ-2026_L2/20261021.parquet';pf=pq.ParquetFile(file)
    opcounts=np.zeros(3,dtype=np.int64);zeros=np.zeros(3,dtype=np.int64);prev=None;negative=0;maxpos=0;null_mm=0
    sample=[]
    for b in pf.iter_batches(batch_size=500000):
        t=b.column('Timestamp').cast('int64').to_numpy();op=b.column('Operation').to_numpy();pos=b.column('Position').to_numpy();vol=b.column('Volume').to_numpy()
        negative+=int(np.sum(np.diff(t)<0))+(int(t[0]<prev) if prev is not None else 0);prev=t[-1];maxpos=max(maxpos,int(pos.max()))
        null_mm+=b.column('MarketMaker').null_count
        for k in range(3):opcounts[k]+=int(np.sum(op==k));zeros[k]+=int(np.sum((op==k)&(vol==0)))
        if not sample:sample=b.slice(0,25).to_pylist()
    # Ladder reconstruction is intentionally not claimed: the chosen model needs L1 best quotes only.
    return dict(source=str(file),sha256=file_hash(file),schema=str(pf.schema_arrow),rows=pf.metadata.num_rows,
        operation_counts=opcounts.tolist(),zero_volume_by_operation=zeros.tolist(),max_position=maxpos,negative_timestamp_steps=negative,
        marketmaker_null_rows=null_mm,first_events=sample,operation_mapping='Decoder0=Add,1=Update,2=Remove; position-based event stream, not standalone full snapshots',
        reconstruction_validated=False,limitation='Missing shared L1/L2 ordinal and reset markers; initial Add ladder is snapshot-like but later rows are increments. No depth-based OFI claim.')

def main():
    manifest=json.loads((ROOT/'research/ofi-feasibility-manifest.json').read_text());reports=[];folder=ROOT/'data/runner/ofi';folder.mkdir(exist_ok=True)
    for day in manifest['dates']:
        report,features=audit_day(day);reports.append(report);atomic(folder/(day+'.minutes.json'),features)
        atomic(ROOT/'research/ofi-l1-quality.json',reports)
        print(json.dumps({k:report[k] for k in ('date','integrity_passed','rth_quote_events','crossed_groups','locked_groups','eligible_minutes')}),flush=True)
    depth=audit_depth()
    # Convert only display timestamps; numeric feature timestamps stay integer UTC nanoseconds.
    for row in depth['first_events']:row['Timestamp']=row['Timestamp'].isoformat()
    atomic(ROOT/'research/ofi-l2-quality.json',depth)
    print(json.dumps(dict(l2_rows=depth['rows'],operations=depth['operation_counts'],reconstruction_validated=False)),flush=True)

if __name__=='__main__':main()
