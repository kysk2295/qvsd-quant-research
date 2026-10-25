"""Deduplicate cost/fill repeats; summarize observed native inactivity evidence."""
import json
from collections import defaultdict
from runner.core import ROOT,atomic

def main():
    docs=[]
    for phase in ('development','recent','high-resolution'):
        path=ROOT/'data/runner'/('cafe-'+phase+'-20261025.json')
        docs.extend(json.loads(path.read_text()))
    for path in (ROOT/'data/runner/cafe-extension').glob('*.json'):
        r=json.loads(path.read_text())
        if r.get('ack') and r.get('doc'):docs.append(r['doc'])
    sessions={}
    for doc in docs:
        if doc['settings']['slippageTicks']!=2:continue
        variant=doc['inputs']['Variant'];minutes=60 if variant==3 else doc['inputs']['RangeMinutes']
        output=doc.get('output') or []
        for line in output:
            if not line.startswith('AUDIT '):continue
            fields=line.split();day=fields[1];audit=dict(p.split('=') for p in fields[2:])
            counter_lines=[s for s in output if s.startswith('COUNTS '+day+' ')]
            counters=dict((k,int(v)) for p in counter_lines for k,v in (part.split('=') for part in p.split()[2:]))
            risk_lines=[s for s in output if s.startswith('SIZE_REJECT '+day+' ')]
            row=dict(date=day,variant=variant,range_minutes=minutes,entries=int(audit['entries']),gap=audit['gap'],
                reported_bars=int(audit['bars']),size_rejections=len(risk_lines),condition_counts=counters or None,
                qualified_pattern_lower_bound=int(audit['entries'])+len(risk_lines),
                full_condition_counts_available=bool(counter_lines),
                basis='One base-cost observation per date and configuration; stress/fill duplicates excluded')
            key=(day,variant,minutes)
            if key not in sessions or row['full_condition_counts_available']:sessions[key]=row
    groups=defaultdict(list)
    for row in sessions.values():groups[(row['variant'],row['range_minutes'])].append(row)
    summary=[]
    for (variant,minutes),rows in sorted(groups.items()):
        counts=defaultdict(int)
        for row in rows:
            for k,v in (row['condition_counts'] or {}).items():counts[k]+=v
        summary.append(dict(variant=variant,range_minutes=minutes,distinct_sessions=len(rows),
            active_sessions=sum(r['entries']>0 for r in rows),entries=sum(r['entries'] for r in rows),
            size_rejections=sum(r['size_rejections'] for r in rows),
            instrumented_sessions=sum(r['full_condition_counts_available'] for r in rows),
            instrumented_counts=dict(counts),sessions=sorted(rows,key=lambda r:r['date']),
            limitation='Older logs lack full signal/filter counts. No-trade days cannot automatically be called no-signal days. Qualified-pattern counter overlaps its subsequent outcomes.'))
    atomic(ROOT/'research/cafe-condition-summary.json',summary)
    print(json.dumps([{k:v for k,v in r.items() if k!='sessions'} for r in summary]),flush=True)

if __name__=='__main__':main()
