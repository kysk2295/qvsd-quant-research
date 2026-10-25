"""Freeze prior-session close and volatility from real Last ticks, before native tests."""
import json,statistics
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from runner.core import ROOT,atomic,file_hash

NY=ZoneInfo('America/New_York')
def previous_weekday(value):
    day=datetime.fromisoformat(value).date()-timedelta(days=1)
    while day.weekday()>=5:day-=timedelta(days=1)
    return day.isoformat()

def main():
    manifest=json.loads((ROOT/'research/gap-fade-manifest.json').read_text());dates=manifest['data_requirements']['recent']
    needed=sorted(set(dates+[previous_weekday(d) for d in dates]));sessions={};sources=[]
    audit=json.loads((ROOT/'research/recent-tick-audit-20261025.json').read_text())
    bydate={s['date']:r for r in audit for s in r['sessions'] if s['minutes']==390 and not s['missingMinutes']}
    for day in needed:
        assert day in bydate,'Missing required RTH ticks '+day
        file=ROOT/bydate[day]['file'];assert file_hash(file)==bydate[day]['sha256']
        minutes={};previous=None;local=None
        for line in file.open(encoding='ascii'):
            stamp,price,size=line.strip().split(';')
            key=stamp[:13]
            if key!=previous:
                local=datetime.strptime(key,'%Y%m%d %H%M').replace(tzinfo=timezone.utc).astimezone(NY);previous=key
            minute=local.hour*60+local.minute
            if str(local.date())==day and 570<=minute<960:
                price=float(price)
                if minute not in minutes:minutes[minute]={'open':price,'close':price}
                else:minutes[minute]['close']=price
        assert set(minutes)==set(range(570,960))
        sessions[day]=dict(open=minutes[570]['open'],close=minutes[959]['close'],last60=[minutes[m]['close'] for m in range(900,960)])
        sources.append(dict(date=day,path=str(file),sha256=bydate[day]['sha256']))
    rows=[]
    for day in dates:
        prev=previous_weekday(day);closes=sessions[prev]['last60'];sigma=statistics.pstdev(closes)
        delta=sessions[day]['open']-sessions[prev]['close']
        rows.append(dict(date=day,previous_date=prev,previous_close=sessions[prev]['close'],open=sessions[day]['open'],
            sigma=sigma,delta=delta,threshold=-3*sigma,qualified=sigma>0 and delta<-3*sigma,last60_closes=closes))
    atomic(ROOT/'research/gap-fade-coverage.json',dict(complete=True,sources=sources,observations=rows,
        calendar='Weekdays for the explicitly registered October2026 window; no exchange RTH closure in these dates; not a general holiday calendar',
        limitation='Last-tick minute aggregation, not bid/ask or lossless completeness; native context must match independently.'))
    print(json.dumps(dict(complete=True,covered_rth_days=len(needed),evaluation_days=len(rows))))

if __name__=='__main__':main()
