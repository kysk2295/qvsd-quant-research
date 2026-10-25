"""In-memory tracing of the hash-pinned decoder, without changing its semantics.

The runtime decoder derives from nt8-mcp / cli-nt-bridge. Its source is read from
the installed module, never copied over or altered on disk. This is instrumentation,
not an independent format oracle or a corrected market-data decoder.
"""
import inspect
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import numpy as np


def calendar_summary(ts, prices, volumes, day):
    ny = ZoneInfo('America/New_York')
    opening = int(datetime.fromisoformat(day+'T09:30').replace(tzinfo=ny).timestamp())*10**9
    closing = opening+390*60*10**9
    selected = (ts >= opening) & (ts < closing)
    minutes = sorted(set(int(v) for v in ((ts[selected]-opening)//(60*10**9))))
    groups = {'UTC':{},'America/New_York':{}}
    for stamp,vol in zip(ts,volumes):
        dt = datetime.fromtimestamp(int(stamp)/1e9,timezone.utc)
        for zone,clock in (('UTC',dt),('America/New_York',dt.astimezone(ny))):
            key=clock.date().isoformat(); row=groups[zone].setdefault(key,dict(date=key,last_records=0,last_volume=0))
            row['last_records']+=1; row['last_volume']+=int(vol)
    return dict(last_calendar_day_totals={z:[v for k,v in sorted(ds.items())] for z,ds in groups.items()},
                rth_minutes=len(minutes),rth_missing_minutes=sorted(set(range(390))-set(minutes)),
                rth_ticks=int(selected.sum()),rth_volume=int(volumes[selected].sum()))


def traced_decode(module, buf, slots):
    """One full strict decode with record-offset observations; no parameter search."""
    first_bad={}; previous={}; first_records={}; encoding_counts={}
    def observe(i,j,m1,m2,info,t,c,vol,mdt,k1,k2):
        if info & 0xC0 != 0xC0:
            return
        h=slots[mdt]; tick=next(s['tick'] for s in slots if s['count'])
        price=c*tick
        signature=f'ts:{m1&7},price:{m1&24},nibble:{bool(m2&31)},volume:{(m1>>5)&7},type:{mdt}'
        encoding_counts[signature]=encoding_counts.get(signature,0)+1
        if mdt in first_bad:
            return
        record=dict(l1_index=k1-1,stream_offset=i,file_offset=i+3520,record_bytes=j-i,
                    m1=m1,m2=m2,info=info,timestamp_ticks=t,price=price,volume=vol,
                    timestamp_mode=m1&7,price_mode=m1&24,price_nibble=m2&31,volume_mode=(m1>>5)&7)
        if mdt not in first_records:
            first_records[mdt]=record
        if price < h['pmin']-1e-6 or price > h['pmax']+1e-6:
            first_bad[mdt]=dict(header=h,previous_same_type=previous.get(mdt),record=record)
        previous[mdt]=record
    source=inspect.getsource(module.decode)
    needle='            i = j\n'
    if source.count(needle)!=1:
        raise ValueError('Pinned decoder trace hook no longer unique')
    replacement='            observe(i,j,m1,m2,info,t,c,vol,mdt if (info & 0xC0 == 0xC0) else None,k1,k2)\n'+needle
    namespace=dict(module.__dict__,observe=observe)
    exec(compile(source.replace(needle,replacement),'<hash-pinned-nrd-trace>','exec'),namespace)
    decoded=namespace['decode'](buf,slots,want_l1=True,want_l2=True,salvage=False)
    return decoded,dict(first_outside_header=first_bad,first_records=first_records,
                        encoding_counts=encoding_counts,stream_bytes=len(buf),
                        scope='Exact original decoder with one observation hook; not independent decoding')
