"""Pre-outcome preparation of final bounded OFI historical extension."""
import json,time
from datetime import datetime,timezone
from collections import defaultdict
from zoneinfo import ZoneInfo
import numpy as np
import pyarrow.parquet as pq
from runner.core import ROOT,atomic,file_hash
from runner.research_lifecycle import Lifecycle
from research.prepare_nt_ticks import prepare

def main():
    Lifecycle().update('auditing','Final OFI extension Oct2: freeze rule/stop criteria, audit Last coverage and7quote exclusions',None)
    m=json.loads((ROOT/'research/ofi-oct5-manifest.json').read_text());m['created_at']=time.time()
    m['chronological_split'].update(dates=['2026-10-02'],policy='Newly acquired historical extension; no repeat of14evaluated sessions, not prospective/OOS')
    m['data_requirements'].update(recent=['2026-10-02'],recent_request_from='2026-10-01',recent_request_to='2026-10-03')
    m['extension_stop_rule']='This ends current historical date-extension campaign after at most15sessions/10native cost runs. If combined high-fee plus4ticks/fill net<=0 or best-day-excluded high-fee net<=0, stop routine date extensions and classify fixed candidate adoption gate unmet. No parameter retuning. Reopen only under distinct preregistered research question/data regime; move to MACD cross hypothesis next.'
    atomic(ROOT/'research/ofi-oct2-manifest.json',m)
    source=ROOT/'data/incoming/replay/2026/NQ-2026_L1/20261002.parquet';dest=ROOT/'data/runner/nt-import/20261002/NQ DEC26.Last.txt'
    prep=prepare(source,dest);atomic(ROOT/'research/ofi-oct2-tick-preparation.json',prep)
    minutes=defaultdict(int);prev='';lastminute=None;count=volume=0
    for line in dest.open():
        stamp,price,size=line.strip().split(';');assert stamp>=prev;prev=stamp;price=float(price);size=int(size)
        assert size>0 and price>0 and abs(price*4-round(price*4))<1e-8
        if stamp[:13]!=lastminute:lastminute=stamp[:13];dt=datetime.strptime(lastminute,'%Y%m%d %H%M').replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/New_York'));minute=dt.hour*60+dt.minute
        if str(dt.date())=='2026-10-02' and 570<=minute<960:minutes[minute]+=size
        count+=1;volume+=size
    assert len(minutes)==390
    row=dict(file=str(dest.relative_to(ROOT)),sha256=file_hash(dest),ticks=count,volume=volume,sessions=[dict(date='2026-10-02',minutes=390,rthVolume=sum(minutes.values()),missingMinutes=[])])
    p=ROOT/'research/recent-tick-audit-20261025.json';old=json.loads(p.read_text());assert not any(x['file']==row['file'] for x in old);old.append(row);atomic(p,old);atomic(ROOT/'research/ofi-oct2-tick-audit.json',row)
    features=json.loads((ROOT/'data/runner/ofi/2026-10-02.minutes.json').read_text());opening=features[0]['end_utc_ns']-60*10**9;parts={0:[],1:[]}
    for b in pq.ParquetFile(source).iter_batches(batch_size=500000,columns=['Timestamp','MarketDataType']):
        ts=b.column(0).cast('int64').to_numpy();kind=b.column(1).to_numpy()
        for side in parts:parts[side].append(ts[(kind==side)&(ts>=opening)])
    arrays={s:np.concatenate(x) for s,x in parts.items()};excluded=[]
    for index,f in enumerate(features):
        end=f['end_utc_ns'];reasons=[];ages={}
        for side,ts in arrays.items():
            i=np.searchsorted(ts,end,'left')-1;ages[side]=end-int(ts[i]) if i>=0 else None
            if i<0:reasons.append('missing_side_at_boundary')
            elif ages[side]>10**9:reasons.append('side_stale_at_boundary')
        if index==0 and arrays[0][0]!=arrays[1][0]:reasons.append('initial_group_missing_side')
        for key in ('stale_groups','crossed_groups','locked_groups'):
            if f[key]:reasons.append(key)
        if f['max_group_gap_ns']>10**9:reasons.append('intergroup_gap_over1s')
        if f['ask_updates']==0 or f['bid_updates']==0:reasons.append('side_without_update')
        assert f['eligible']==(not reasons) and f['last_source_ns']<end
        if reasons:excluded.append(dict(minute_index=index,end_utc_ns=end,last_source_ns=f['last_source_ns'],reasons=reasons,boundary_age_ns=ages))
    assert len(features)==390 and len(excluded)==7
    atomic(ROOT/'research/ofi-oct2-exclusions.json',dict(eligible=383,excluded=7,rows=excluded,quality_recalculation_match=True,causality='Only timestamps before feature end and age at boundary; applied60seconds later. No future quotes/returns/outcomes. Original integrity is offline coverage gate.'))
    p=ROOT/'data/runner/ofi/oct2-features.csv';assert not p.exists();lines=['end_utc_ns;eligible;ofi;mean_depth;last_source_ns;spread_ticks']
    for f in features:
        spread=(f['end_ask']-f['end_bid'])/.25 if f['end_ask'] is not None and f['end_bid'] is not None else -1
        lines.append(';'.join(map(str,[f['end_utc_ns'],int(f['eligible']),f['ofi'],f['mean_depth'],f['last_source_ns'] or 0,spread])))
    p.write_text('\n'.join(lines)+'\n',encoding='ascii');h=file_hash(p)
    atomic(ROOT/'research/ofi-oct2-coverage.json',dict(complete=True,path=str(p),sha256=h,rows=390,eligible_rows=383,raw_quality='research/ofi-oct2-quality.json',tick_quality='research/ofi-oct2-tick-audit.json'))
    oldhash=json.loads((ROOT/'research/ofi-oct5-coverage.json').read_text())['sha256']
    s=(ROOT/'native/CodexQuoteOfiOct5.cs').read_text().replace('CodexQuoteOfiOct5','CodexQuoteOfiOct2').replace('CodexOfiOct5Gate','CodexOfiOct2Gate').replace(oldhash,h).replace('oct5-features.csv','oct2-features.csv')
    (ROOT/'native/CodexQuoteOfiOct2.cs').write_text(s,encoding='utf-8')
    print(json.dumps(dict(ticks=count,rth_minutes=390,eligible=383,excluded=7,feature_sha256=h,native_budget=2)))

if __name__=='__main__':main()
