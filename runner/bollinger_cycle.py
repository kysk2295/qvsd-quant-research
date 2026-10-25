import json,math
from collections import deque
from .rsi_cycle import RsiCycle
from .core import ROOT,ProcessLock,atomic

class BollingerCycle(RsiCycle):
    strategy='CodexBollingerReturn';parameter='BandLength';bars_value=1;rth_bars=390;requires_eth=False
    manifest_name='bollinger-return-manifest.json';folder_name='bollinger-return';result_name='bollinger-return-results.json';id_prefix='bollinger-return-';batch='bollinger-return-v1'
    def validate_native(self,doc):
        closes=deque(maxlen=20);day=None;prior=None;rows=0
        for line in doc['output']:
            if not line.startswith('BAR '):continue
            p=line.split();d=p[1][:10];v=dict(x.split('=',1) for x in p[2:])
            if d!=day:day=d;closes.clear();prior=None
            close=float(v['close']);closes.append(close);side=0
            if len(closes)==20:
                mean=sum(closes)/20;dev=2*math.sqrt(sum((c-mean)**2 for c in closes)/20);lo=mean-dev;hi=mean+dev
                for k,x in [('mean',mean),('lower',lo),('upper',hi)]:assert abs(float(v[k])-x)<1e-7
                if prior:side=1 if prior[0]<=prior[1] and close>lo else -1 if prior[0]>=prior[2] and close<hi else 0
                prior=(close,lo,hi)
            assert int(v['side'])==side;rows+=1
        assert rows==13*390
    def run(self):
        with ProcessLock(self.folder/'cycle.lock'):
            rows=[]
            for slip in (2,4):
                r=self.run_one('recent',20,slip);rows.append(r)
                if r['assessment']['decision']=='execution_error':break
            atomic(ROOT/'research'/self.result_name,[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows])
            assert len(rows)==2 and all(r['assessment']['decision']!='execution_error' for r in rows)

if __name__=='__main__':
    c=BollingerCycle()
    try:c.run()
    except Exception as e:c.lifecycle.update('failed',str(e),None);raise
    c.lifecycle.update('reviewing','Bollinger2native runs persisted; reviewing independent bar math and ledgers',None)
