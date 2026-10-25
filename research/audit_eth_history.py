"""Check observed five-minute intervals against the installed CME ETH schedule."""
import json
import xml.etree.ElementTree as ET
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from runner.core import ROOT,atomic,file_hash

CT=ZoneInfo('America/Chicago');NY=ZoneInfo('America/New_York');UTC=ZoneInfo('UTC')
def scheduled(stamp):
    local=stamp.astimezone(CT);day=local.weekday();minute=local.hour*60+local.minute
    if day==5:return False
    if day==6:return minute>=17*60
    if day==4:return minute<16*60
    return minute<16*60 or minute>=17*60

def main():
    template=Path.home()/'Documents/NinjaTrader 8/templates/TradingHours/CME US Index Futures ETH.xml'
    tree=ET.parse(template)
    assert tree.findtext('.//TimeZone')=='Central Standard Time'
    sessions=[(s.findtext('BeginDay'),s.findtext('BeginTime'),s.findtext('EndDay'),s.findtext('EndTime')) for s in tree.findall('.//Sessions/Session')]
    expected=[(a,'1700',b,'1600') for a,b in zip(('Sunday','Monday','Tuesday','Wednesday','Thursday'),('Monday','Tuesday','Wednesday','Thursday','Friday'))]
    assert sessions==expected,'Trading schedule differs; inspect before auditing'
    holidays=[n.text for n in tree.findall('.//Date') if n.text and '2026-10-09'<=n.text[:10]<='2026-10-22']
    assert not holidays,'Holiday exception needs explicit evaluation'
    observed=set();sources=[]
    for file in sorted((ROOT/'data/runner/nt-import').glob('202610*/NQ DEC26.Last.txt')):
        day=file.parent.name
        if not '20261009'<=day<='20261022':continue
        minutes=set()
        for line in file.open(encoding='ascii'):minutes.add(line[:13])
        for minute in minutes:
            stamp=datetime.strptime(minute,'%Y%m%d %H%M').replace(tzinfo=UTC)
            observed.add(stamp.replace(minute=stamp.minute//5*5))
        sources.append(dict(path=str(file),sha256=file_hash(file),observed_minutes=len(minutes)))
    dates=['2026-10-'+d for d in ('12','13','14','15','16','19','20','21','22')]
    warmups=[];earliest=None
    for date in dates:
        opening=datetime.fromisoformat(date+'T09:30:00').replace(tzinfo=NY).astimezone(UTC)
        stamp=opening-timedelta(minutes=5);needed=[]
        while len(needed)<200:
            if scheduled(stamp):needed.append(stamp)
            stamp-=timedelta(minutes=5)
        missing=[s.isoformat() for s in sorted(needed) if s not in observed]
        earliest=min(needed) if earliest is None else min(earliest,min(needed))
        warmups.append(dict(date=date,required_bars=200,observed_bars=200-len(missing),missing_intervals=missing))
    end=datetime.fromisoformat('2026-10-22T16:00:00').replace(tzinfo=NY).astimezone(UTC)
    stamp=earliest;missing=[];total=0
    while stamp<end:
        if scheduled(stamp):
            total+=1
            if stamp not in observed:missing.append(stamp.isoformat())
        stamp+=timedelta(minutes=5)
    report=dict(version=1,schedule='Installed CME US Index Futures ETH; Sun17CT-Fri16CT; daily16-17CT maintenance',template_sha256=file_hash(template),
        sources=sources,warmup=warmups,expected_intervals=total,missing_intervals=missing,
        complete=not missing and all(w['observed_bars']==200 for w in warmups),
        limitation='Observed Last ticks establish nonempty5minute intervals, not lossless tick completeness or bid/ask coverage. Native warmup counters must also pass.',
        independent_oos=False)
    atomic(ROOT/'research/rsi-eth-coverage-v2.json',report)
    print(json.dumps(dict(complete=report['complete'],expected=total,missing=len(missing),warmup=[{'date':w['date'],'bars':w['observed_bars']} for w in warmups])),flush=True)

if __name__=='__main__':main()
