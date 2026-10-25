"""Build independent minuteOHLC from hashed audited Last files, no returns."""
import json
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from runner.core import ROOT,atomic,file_hash

def main():
    out=ROOT/'research/stochastic-coverage.json';assert not out.exists()
    m=json.loads((ROOT/'research/stochastic-manifest.json').read_text());audit=json.loads((ROOT/'research/recent-tick-audit-20261025.json').read_text())
    byday={s['date']:r for r in audit for s in r['sessions'] if s['minutes']==390 and not s['missingMinutes']};sessions={};sources=[]
    for day in m['data_requirements']['recent']:
        a=byday[day];p=ROOT/a['file'];assert file_hash(p)==a['sha256'];bars={};prev=None
        for line in p.open(encoding='ascii'):
            stamp,price,size=line.strip().split(';');key=stamp[:13]
            if key!=prev:
                prev=key;dt=datetime.strptime(key,'%Y%m%d %H%M').replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/New_York'));minute=dt.hour*60+dt.minute
            if dt.date().isoformat()!=day or not 570<=minute<960:continue
            price=float(price);size=int(size)
            if minute not in bars:bars[minute]=dict(open=price,high=price,low=price,close=price,volume=size)
            else:
                b=bars[minute];b.update(high=max(b['high'],price),low=min(b['low'],price),close=price,volume=b['volume']+size)
        assert sorted(bars)==list(range(570,960));sessions[day]=bars;sources.append(dict(date=day,path=str(p),sha256=a['sha256']))
    atomic(out,dict(complete=True,sessions=sessions,sources=sources,timezone='America/New_York',native_runs=0,independent_oos=False));print('15sessions/5850rawLast minutes audited')

if __name__=='__main__':main()
