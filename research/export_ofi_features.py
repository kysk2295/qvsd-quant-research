"""Freeze audited minute quote features for historical-only NinjaScript consumption."""
import json
from runner.core import ROOT,atomic,file_hash

def main():
    manifest=json.loads((ROOT/'research/ofi-signal-manifest.json').read_text());quality=json.loads((ROOT/'research/ofi-l1-quality.json').read_text())
    assert all(r['integrity_passed'] for r in quality)
    path=ROOT/'data/runner/ofi/bestquote-features.csv';assert not path.exists(),'Frozen file already exists'
    lines=['end_utc_ns;eligible;ofi;mean_depth;last_source_ns;spread_ticks'];inputs=[];total=eligible=0
    for date in manifest['data_requirements']['recent']:
        p=ROOT/f'data/runner/ofi/{date}.minutes.json';rows=json.loads(p.read_text());assert len(rows)==390
        for r in rows:
            assert r['last_source_ns'] is None or r['last_source_ns']<r['end_utc_ns']
            spread=(r['end_ask']-r['end_bid'])/.25 if r['end_ask'] is not None and r['end_bid'] is not None else -1
            lines.append(';'.join(map(str,[r['end_utc_ns'],int(r['eligible']),r['ofi'],r['mean_depth'],r['last_source_ns'] or 0,spread])))
            total+=1;eligible+=r['eligible']
        inputs.append(dict(date=date,path=str(p),sha256=file_hash(p)))
    path.write_text('\n'.join(lines)+'\n',encoding='ascii')
    report=dict(complete=True,path=str(path),sha256=file_hash(path),rows=total,eligible_rows=eligible,inputs=inputs,
        raw_quote_sources=[dict(date=r['date'],sha256=r['source_sha256'],nrd_sha256=r['nrd_sha256']) for r in quality],
        feature_definition='Recorded L1 best-queue OFI per finished minute / mean depth at completed timestamp groups; no Last/DailyVolume or future-return input',
        causality='Each feature uses source timestamps strictly before its own end; strategy decision requires feature end exactly60s before decision. Dataset includes future rows but only exact past key is consulted.')
    atomic(ROOT/'research/ofi-signal-coverage.json',report)
    print(json.dumps(dict(rows=total,eligible=eligible,sha256=report['sha256'])))

if __name__=='__main__':main()
