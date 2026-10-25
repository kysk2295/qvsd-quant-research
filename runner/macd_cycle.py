from .rsi_cycle import RsiCycle
from .core import ROOT,ProcessLock,atomic

class MacdCycle(RsiCycle):
    strategy='CodexMacdCross';parameter='SlowLength';bars_value=1;rth_bars=390;requires_eth=False
    manifest_name='macd-cross-manifest.json';folder_name='macd-cross';result_name='macd-cross-results.json';id_prefix='macd-cross-';batch='macd-cross-v1'
    def validate_native(self,doc):
        day=None;fast=slow=signal=hist=0;count=rows=0
        for line in doc['output']:
            if not line.startswith('MACD '):continue
            x=line.split();d=x[1][:10];v=dict(z.split('=',1) for z in x[2:]);close=float(v['close'])
            if d!=day:day=d;count=0;fast=slow=signal=hist=0
            count+=1;previous=hist
            if count==1:fast=slow=close;signal=hist=0
            else:
                fast+=(close-fast)*2/13;slow+=(close-slow)*2/27;signal+=((fast-slow)-signal)*2/10;hist=fast-slow-signal
            side=1 if previous<=0 and hist>0 else -1 if previous>=0 and hist<0 else 0
            for k,n in [('fast',fast),('slow',slow),('signal',signal),('hist',hist)]:assert abs(float(v[k])-n)<1e-7
            assert int(v['side'])==side;rows+=1
        assert rows==5850
        assert len([s for s in doc['output'] if s.startswith('CLOCK_EXEC|')])==2*len(doc['trades'])
    def run(self):
        with ProcessLock(self.folder/'cycle.lock'):
            rows=[]
            for slip in (2,4):
                r=self.run_one('recent',26,slip);rows.append(r)
                if r['assessment']['decision']=='execution_error':break
            atomic(ROOT/'research'/self.result_name,[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows])
            assert len(rows)==2 and all(r['assessment']['decision']!='execution_error' for r in rows)

if __name__=='__main__':
    c=MacdCycle()
    try:c.run()
    except Exception as e:c.lifecycle.update('failed',str(e),None);raise
    c.lifecycle.update('reviewing','MACD2native runs persisted; independently reviewing raw bars and precise simulated ledgers',None)
