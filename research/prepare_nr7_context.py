import json
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from runner.core import ROOT,atomic,file_hash

def main():
    m=json.loads((ROOT/'research/nr7-rth-manifest.json').read_text());dates=m['data_requirements']['all_context_dates']
    audit=json.loads((ROOT/'research/recent-tick-audit-20261025.json').read_text());bydate={s['date']:r for r in audit for s in r['sessions'] if s['minutes']==390 and not s['missingMinutes']};days=[];sources=[];minute_closes={}
    for day in dates:
        a=bydate[day];p=ROOT/a['file'];assert file_hash(p)==a['sha256'];prev=None;minutes={}
        for line in p.open(encoding='ascii'):
            stamp,price,size=line.strip().split(';');key=stamp[:13]
            if key!=prev:prev=key;dt=datetime.strptime(key,'%Y%m%d %H%M').replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/New_York'));minute=dt.hour*60+dt.minute
            if str(dt.date())==day and 570<=minute<960:
                price=float(price)
                if minute not in minutes:minutes[minute]=dict(high=price,low=price,close=price)
                else:minutes[minute].update(high=max(minutes[minute]['high'],price),low=min(minutes[minute]['low'],price),close=price)
        assert len(minutes)==390
        row=dict(date=day,high=max(v['high'] for v in minutes.values()),low=min(v['low'] for v in minutes.values()),close=minutes[959]['close']);row['range']=row['high']-row['low'];days.append(row)
        minute_closes[day]={str(k):v['close'] for k,v in minutes.items()};sources.append(dict(date=day,path=str(p),sha256=a['sha256']))
    setups=[]
    for i in range(7,len(days)):
        prior=days[i-7:i];qualified=prior[-1]['range']>0 and all(prior[-1]['range']<x['range'] for x in prior[:-1])
        setups.append(dict(date=days[i]['date'],prior_dates=[x['date'] for x in prior],qualified=qualified,prior_high=prior[-1]['high'],prior_low=prior[-1]['low'],prior_date=prior[-1]['date']))
    atomic(ROOT/'research/nr7-rth-coverage.json',dict(complete=True,sessions=days,sources=sources,setups=setups,minute_closes=minute_closes,role='7warmup sessions and8historical evaluation sessions;notOOS',native_runs=0))
    print(json.dumps(dict(complete=True,warmup_sessions=7,evaluation_sessions=8,qualified_sessions=[s['date'] for s in setups if s['qualified']])))

if __name__=='__main__':main()
