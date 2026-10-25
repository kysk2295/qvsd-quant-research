"""Validate run evidence and publish aggregates without promoting failed candidates."""
import json,hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
root=Path(__file__).resolve().parents[1]
ny=ZoneInfo('America/New_York'); kr=ZoneInfo('Asia/Seoul')
rows=[]
for phase,filename,dates in [('development','cafe-development-20261025.json',{'20260929','20260930','20261001','20261002','20261005','20261006'}),
                             ('recent','cafe-recent-20261025.json',{'20261019','20261020','20261021','20261022'})]:
    runs=json.loads((root/'data/runner'/filename).read_text(encoding='utf-8'))
    for d in runs:
        assert d['state']=='done' and d['error'] is None and d['tickReplay'] is False
        assert d['settings']['fillResolution']=='Standard' and d['settings']['includeCommission'] is False
        assert not any('ORDER_ERROR' in x for x in d['output'])
        audits=[x for x in d['output'] if x.startswith('AUDIT ')]
        assert {x.split()[1] for x in audits}==dates and all('gap=False' in x for x in audits)
        assert len(d['trades'])==d['summary']['trades']
        for t in d['trades']:
            entry=datetime.fromisoformat(t['entryTime']).replace(tzinfo=kr).astimezone(ny)
            assert entry.strftime('%Y%m%d') in dates and t['qty']==1
        fee=5 if d['settings']['slippageTicks']==2 else 10
        pnl=[t['pnl']-fee*t['qty'] for t in d['trades']]
        rejected=[float(x.split('risk=')[1]) for x in d['output'] if x.startswith('SIZE_REJECT ')]
        rows.append(dict(phase=phase,variant=d['inputs']['Variant'],rangeMinutes=d['inputs']['RangeMinutes'],
                         slippageTicks=d['settings']['slippageTicks'],assumedRoundTripFee=fee,
                         trades=len(pnl),nativeNet=d['summary']['netProfit'],netAfterAssumedFee=sum(pnl),
                         sizeRejected=len(rejected),minRejectedRisk=min(rejected) if rejected else None,
                         sameBarTrades=sum(t['entryTime']==t['exitTime'] for t in d['trades']),
                         barsFrom=d['barsFrom'],barsTo=d['barsTo'],auditDays=len(audits)))
result=dict(sourceSha256=hashlib.sha256((root/'native/CodexCafeRange.cs').read_bytes()).hexdigest(),
            candidatesPassed=0,independentHoldout=False,rows=rows,
            conclusion='Insufficient development trades; all recent signals rejected by fixed NQ risk budget. No strategy promoted to Replay.')
(root/'research/cafe-cycle-results-20261025.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
