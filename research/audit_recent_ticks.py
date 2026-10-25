"""Audit real Last ticks; session completeness is checked before evaluating trades."""
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
root=Path(__file__).resolve().parents[1]
ny=ZoneInfo('America/New_York')
rows=[]
for file in sorted((root/'data/runner/nt-import').glob('*/NQ DEC26.Last.txt')):
    sessions=defaultdict(lambda: defaultdict(int)); previous=''; count=volume=0
    for line in file.open(encoding='ascii'):
        stamp,price,size=line.strip().split(';')
        assert stamp>=previous;previous=stamp
        price=float(price);size=int(size)
        assert price>0 and size>0 and abs(price*4-round(price*4))<1e-8
        local=datetime.strptime(stamp[:15],'%Y%m%d %H%M%S').replace(tzinfo=timezone.utc).astimezone(ny)
        minute=local.hour*60+local.minute
        if 570<=minute<960:sessions[str(local.date())][minute]+=size
        count+=1;volume+=size
    rows.append(dict(file=str(file.relative_to(root)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                     ticks=count,volume=volume,sessions=[dict(date=d,minutes=len(m),rthVolume=sum(m.values()),
                     missingMinutes=sorted(set(range(570,960))-set(m))) for d,m in sorted(sessions.items())]))
out=root/'research/recent-tick-audit-20261025.json'
out.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rows,indent=2))
