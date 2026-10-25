"""Truthful finite research worker lifecycle, persisted and published separately."""
import json,time
from .core import ROOT,atomic
from dashboard.reporter import post

class Lifecycle:
    def __init__(self):
        self.config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text(encoding='utf-8'))
    def update(self,phase,message,current_run=None):
        event=dict(id='windows-candidate-research',label='Windows NQ candidate research',
                   phase=phase,current_run=current_run,message=message,updated_at=time.time(),
                   continuously_running=False)
        atomic(ROOT/'research/worker-lifecycle.json',event)
        response=post(self.config['url'],'/api/heartbeat',event,self.config['token'])
        if response.get('ok') is not True:raise RuntimeError('Lifecycle heartbeat ACK missing')
        return event
