import json
from .rsi_cycle import RsiCycle
from .core import ROOT,atomic,ProcessLock

class Nr7Cycle(RsiCycle):
    strategy='CodexNr7Rth';parameter='LookbackDays';bars_value=1;rth_bars=390;requires_eth=False
    manifest_name='nr7-rth-manifest.json';folder_name='nr7-rth';result_name='nr7-rth-results.json';id_prefix='nr7-rth-';batch='nr7-rth-v1';coverage_report_name='nr7-rth-coverage.json'
    def validate_native(self,doc):
        c=json.loads((ROOT/'research'/self.coverage_report_name).read_text());days={x['date'].replace('-',''):x for x in c['sessions']};setups={x['date'].replace('-',''):x for x in c['setups']};seen=set();ready=set()
        for line in doc['output']:
            x=line.split()
            if x[0]=='DAY':
                v=dict(z.split('=',1) for z in x[2:]);expected=days[x[1]];assert v['bars']=='390' and v['gap']=='False' and v['valid']=='True'
                for k in ('high','low','close'):assert float(v[k])==expected[k]
                seen.add(x[1])
            if x[0]=='SETUP':
                v=dict(z.split('=',1) for z in x[2:]);e=setups[x[1]];assert v['priorCount']=='7' and (v['qualified']=='True')==e['qualified'] and v['priorDate']==e['prior_date'].replace('-','')
                assert float(v['high'])==e['prior_high'] and float(v['low'])==e['prior_low'];ready.add(x[1])
        assert seen==set(days) and ready==set(setups)
        assert len([x for x in doc['output'] if x.startswith('CLOCK_EXEC|')])==2*len(doc['trades'])
    def run(self):
        with ProcessLock(self.folder/'cycle.lock'):
            rows=[]
            for slip in (2,4):
                r=self.run_one('recent',7,slip);rows.append(r)
                if r['assessment']['decision']=='execution_error':break
                coverage=json.loads((ROOT/'research'/self.coverage_report_name).read_text())
                if not any(s['qualified'] for s in coverage['setups']) and not r['doc']['trades']:break
            atomic(ROOT/'research'/self.result_name,[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows])
            assert rows and all(r['assessment']['decision']!='execution_error' for r in rows)

if __name__=='__main__':
    c=Nr7Cycle()
    try:c.run()
    except Exception as e:c.lifecycle.update('failed',str(e),None);raise
    c.lifecycle.update('reviewing','Daily-session NR7 finite native validation persisted; auditing condition coverage',None)
