"""Retain evidence while replacing stale scheduling instructions."""
import json,time
from runner.core import ROOT,atomic

def main():
    p=ROOT/'research/evidence-work-queue.json';q=json.loads(p.read_text());changes=[]
    for t in q['tasks']:
        update=None
        if t['id']=='a17b2ae51a2f1d57aca70912':update=dict(status='completed',evidence='research/rsi-extension-oct7-9-summary.json',next_action='Completed unchanged Oct7-9 extension;zero additional trades;no repeat')
        elif t['id']=='05e1d788c41a4d81d5d674c2':update=dict(status='blocked_policy',evidence='research/rsi-playback-preflight.json',next_action='Prior automatic policy review rejected order status access;do not retry Playback/order-control path or alternate route. No replay validated.')
        elif t.get('candidate') in ('rsi2-2','rsi-repair-v2-2','rsi-extension-oct7-9-2') and t.get('status')=='pending':update=dict(status='superseded_by_scoped_task',superseded_by='1266a2fed269c557a5f21792',next_action='Retain historical evidence;future distinct market data only under frozen rules,no same-window rerun')
        elif t.get('candidate')=='bollinger-return-v1-20' and t.get('status')=='pending':update=dict(status='superseded_by_scoped_task',superseded_by='bollinger-cost-distinct-sample-review')
        if update and any(t.get(k)!=v for k,v in update.items()):
            changes.append(dict(id=t['id'],previous_status=t['status'],new_status=update['status']))
            t.setdefault('scheduling_history',[]).append(dict(at=time.time(),status=t.get('status'),next_action=t.get('next_action')));t.update(update)
    new=[dict(id='cafe-broader-constraint-coverage-review',candidate='cafe-positive-data-extension',kind='coverage-plan-review',status='pending',evidence='research/cafe-condition-summary.json',next_action='Review distinct broader regime coverage with unchanged risk cap;preserve12positive sparse legacy records and30zero-trade extensions;no blind daily additions'),dict(id='bollinger-cost-distinct-sample-review',candidate='bollinger-return-v1',kind='cost-and-coverage-plan-review',status='pending',evidence='research/bollinger-return-summary.json',next_action='Define distinct fixed-rule sample and execution-cost evidence;extra4tick sensitivity previously negative;no same-date native rerun,no policy-blocked Playback')]
    for t in new:
        assert (ROOT/t['evidence']).exists()
        if not any(x['id']==t['id'] for x in q['tasks']):q['tasks'].append(t);changes.append(dict(id=t['id'],new_status='pending'))
    q['next_action']='Finish registered NR7 context acquisition and finite distinct-window native batch;preserve CafeRange/Bollinger scoped reviews and RSI prospective-data task. OFI campaign closed;MACD no repeat;Playback policy block unchanged.'
    atomic(p,q)
    p=ROOT/'research/candidate-backlog.json';b=json.loads(p.read_text())
    for c in b['candidates']:
        if c['id']=='bollinger-return-v1':c['next_action']=new[1]['next_action']
        if c['id']=='rsi-pullback-v1':c['next_action']='Preserve sparse fixed-rule evidence;Oct7-9 extension completed withzero newtrades;await post-Oct25 prospective data. Policy-blocked Playback must not be retried.'
    atomic(p,b)
    p=ROOT/'research/preserved-candidate-audit.json';a=json.loads(p.read_text());a.update(resolved_at=time.time(),scheduling_changes=changes,issue_resolution='Completed RSI tasks closed;blocked Playback explicit;generic repeated chains superseded;CafeRange and Bollinger scoped reviews retained;original results unchanged')
    atomic(p,a);print(json.dumps(dict(scheduling_changes=len(changes))))

if __name__=='__main__':main()
