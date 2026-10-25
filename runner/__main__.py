import argparse
import json
from collections import Counter
from .core import Queue, DEFAULT_STATE, DEFAULT_TELEMETRY, atomic
from .worker import Worker

def main():
    p=argparse.ArgumentParser(description='Finite NQ research queue; no live orders')
    p.add_argument('command',choices=['manifest','enqueue','run','once','pause','resume','stop','status'])
    p.add_argument('--state',default=str(DEFAULT_STATE));p.add_argument('--telemetry',default=str(DEFAULT_TELEMETRY))
    p.add_argument('--manifest');a=p.parse_args();q=Queue(a.state,a.telemetry)
    if a.command=='manifest':
        from .manifest import build
        specs=build();path=q.folder/'manifest-v1.json';atomic(path,specs);print(str(path));return
    if a.command=='enqueue':
        from pathlib import Path
        specs=json.loads(Path(a.manifest or q.folder/'manifest-v1.json').read_text(encoding='utf-8'))
        if not 1<=len(specs)<=40:raise ValueError('Batch budget: 1..40 experiments')
        for spec in specs:q.enqueue(spec)
    elif a.command in ('pause','resume','stop'):
        if a.command=='resume' and q.control('uncertain'):raise RuntimeError('Uncertain native submission; inspect before manual resolution')
        q.control('mode',{'pause':'paused','resume':'running','stop':'stopped'}[a.command])
    elif a.command in ('run','once'):Worker(q).run(once=a.command=='once');return
    rows=q.rows()
    print(json.dumps(dict(mode=q.control('mode'),uncertain=q.control('uncertain'),counts=dict(Counter(r['status'] for r in rows)),
                         heartbeat_ack=q.control('heartbeat_ack'),heartbeat_error=q.control('heartbeat_error'),
                         jobs=[{k:r[k] for k in ('id','status','phase','reason','nt_id')} for r in rows]),ensure_ascii=True))

if __name__=='__main__':main()
