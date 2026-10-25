"""Bounded offline diagnostic; no export/import or strategy outcome calculation."""
import json
import argparse
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from runner.core import ROOT, atomic, file_hash
from research.analyze_market_state import read, require

PLAN = 'research/nrd-oct23-quality-plan.json'
PLAN_HASH = 'd11a658de46f0ba8d7a3a2f617ab7edb5df98ab0c0728003b2d8d8e6365fc41f'
REPORT = 'research/nrd-oct23-baseline-diagnostic.json'


def verify(plan):
    require(file_hash(ROOT/PLAN) == PLAN_HASH, 'Registered plan changed')
    for path,digest in plan['immutable_hashes'].items():
        require(file_hash(ROOT/path) == digest, 'Protected artifact changed: '+path)
    for path,digest in plan['source_hashes'].items():
        require(file_hash(path) == digest, 'Original raw file changed: '+path)
    require(file_hash(plan['decoder']) == plan['original_decoder_sha256'], 'Baseline parser changed')


def claim(kind):
    ledger = read('research/campaign-data-analysis-ledger.json')
    entry = next(e for e in ledger['entries'] if e['id'] == 'nq-nrd-oct23-quality-20261025')
    require(not entry['attempts'].get(kind), 'Attempt already reserved: '+kind)
    entry['attempts'][kind] = dict(reserved_at_utc=datetime.now(timezone.utc).isoformat(), count=1)
    entry['status'] = 'diagnosing'
    atomic(ROOT/'research/campaign-data-analysis-ledger.json', ledger)


def utc(ns):
    return datetime.fromtimestamp(int(ns)/1e9, timezone.utc).isoformat()


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--wire',action='store_true'); args=parser.parse_args()
    report='research/nrd-oct23-wire-diagnostic.json' if args.wire else REPORT
    require(not (ROOT/report).exists(), 'Diagnostic already exists')
    plan = read(PLAN); verify(plan); claim('targeted_wire_inspection' if args.wire else 'baseline_full_decode')
    decoder = Path(plan['decoder'])
    sys.path.insert(0, str(decoder.parents[1]))
    from nt8_mcp import nrd_offline as nrd
    source = Path(plan['source']); raw = source.read_bytes()
    header_fields = ('last','count','pmax','pmin','first','one','tick','flag','t0','t1','volsum')
    headers = [dict(zip(header_fields,nrd.HDR.unpack_from(raw,i*80)),slot=i) for i in range(44)]
    print('Strict diagnostic decode starting; metadata only; original files unchanged', flush=True)
    from research.nrd_trace import traced_decode,calendar_summary
    if args.wire:
        decoded,trace=traced_decode(nrd,raw[3520:],nrd.parse_headers(raw[:3520]))
    else:
        decoded=nrd.decode(raw[3520:],nrd.parse_headers(raw[:3520]),want_l1=True,want_l2=True,salvage=False)
        trace=None
    ts,kind,price,volume = decoded['L1']
    rows = []
    anomaly_indices = set()
    for h in headers[:10]:
        k = h['slot']; indices = np.flatnonzero(kind == k)
        if not len(indices) and not h['count']:
            continue
        p,v,t = price[indices],volume[indices],ts[indices]
        outside = (~np.isfinite(p)) | (p < h['pmin']-1e-6) | (p > h['pmax']+1e-6)
        bad = indices[outside]
        anomaly_indices.update(int(i) for i in bad[:2])
        rows.append(dict(slot=k, name=nrd.L1_TYPES[k], header=h, decoded_count=len(indices),
            count_difference=len(indices)-h['count'], decoded_volume=int(v.sum()), volume_difference=int(v.sum())-h['volsum'],
            decoded_first=float(p[0]) if len(p) else None, decoded_last=float(p[-1]) if len(p) else None,
            decoded_min=float(p.min()) if len(p) else None, decoded_max=float(p.max()) if len(p) else None,
            decoded_first_utc=utc(t[0]) if len(t) else None, decoded_last_utc=utc(t[-1]) if len(t) else None,
            header_first_utc=utc((h['t0']-nrd.EPOCH_TICKS)*100) if h['count'] else None,
            header_last_utc=utc((h['t1']-nrd.EPOCH_TICKS)*100) if h['count'] else None,
            outside_header_range_count=len(bad), first_outside_l1_index=int(bad[0]) if len(bad) else None,
            first_outside_utc=utc(ts[bad[0]]) if len(bad) else None,
            first_outside_price=float(price[bad[0]]) if len(bad) else None))
    last = kind == 2
    lt,lp,lv = ts[last],price[last],volume[last]
    calendar=calendar_summary(lt,lp,lv,'2026-10-23')
    same = (ts[1:]==ts[:-1]) & (kind[1:]==kind[:-1]) & (price[1:]==price[:-1]) & (volume[1:]==volume[:-1])
    result = dict(id=plan['id'], created_at_utc=datetime.now(timezone.utc).isoformat(),
        plan_sha256=PLAN_HASH, source_sha256=file_hash(source), source_bytes=len(raw), decoder_sha256=file_hash(decoder),
        legacy_error_reproduced=not decoded['integrity_ok'], integrity_ok=decoded['integrity_ok'],
        integrity_errors=decoded['integrity_errors'], truncated=decoded['truncated'],
        bytes_consumed=len(raw)-3520 if not decoded['truncated'] else None,
        l1_rows=len(ts), l2_rows=len(decoded['L2'][0]), slots=rows,
        active_header_slots=[h for h in headers if h['count']],
        global_first_utc=utc(ts[0]), global_last_utc=utc(ts[-1]),
        backward_timestamp_steps=int(np.sum(np.diff(ts)<0)), equal_timestamp_steps=int(np.sum(np.diff(ts)==0)),
        identical_adjacent_l1_records=int(same.sum()), identical_records_interpretation='No exchange sequence; identical events do not establish accidental duplication',
        last_nonpositive_prices=int(np.sum(lp<=0)), last_nonfinite_prices=int(np.sum(~np.isfinite(lp))),
        last_nonpositive_volumes=int(np.sum(lv<=0)), last_off_tick_prices=int(np.sum(np.abs(lp*4-np.rint(lp*4))>1e-8)),
        **calendar,wire_trace=trace,
        anomaly_l1_indices=sorted(anomaly_indices),
        quality_accepted=False, new_market_artifacts_written=False,
        outputs='Only diagnostic JSON; no parquet/Last export, no old result recomputation',
        code_sha256=file_hash(Path(__file__)))
    verify(plan)
    atomic(ROOT/report,result)
    print(json.dumps({k:result[k] for k in ('integrity_ok','integrity_errors','truncated','l1_rows','l2_rows','rth_minutes','anomaly_l1_indices')}),flush=True)


if __name__ == '__main__':
    main()
