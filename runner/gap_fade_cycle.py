"""Fixed gap-fade setting and two costs; native context independently verified."""
import json
from .rsi_cycle import RsiCycle
from .core import ROOT,ProcessLock,atomic

class GapCycle(RsiCycle):
    strategy='CodexGapFade'
    manifest_name='gap-fade-manifest.json'
    folder_name='gap-fade'
    result_name='gap-fade-results.json'
    id_prefix='gap-fade-'
    batch='gap-fade-v1'
    parameter='GapSigma'
    levels=(3,)
    bars_value=1
    rth_bars=390
    requires_eth=False
    coverage_report_name='gap-fade-coverage.json'
    def validate_native(self,doc):
        expected=json.loads((ROOT/'research'/self.coverage_report_name).read_text())['observations']
        rows={x.split()[1]:dict(p.split('=') for p in x.split()[2:]) for x in doc['output'] if x.startswith('GAP ')}
        assert len(rows)==len(expected)
        for e in expected:
            x=rows[e['date'].replace('-','')]
            assert x['ready']=='True' and x['priorDate']==e['previous_date'].replace('-','')
            for native,key in [('priorClose','previous_close'),('open','open'),('sigma','sigma')]:
                assert abs(float(x[native])-e[key])<1e-6, 'Native/source context differs '+e['date']+' '+key
            assert (x['qualified']=='True')==e['qualified']
    def run(self):
        with ProcessLock(self.folder/'cycle.lock'):
            rows=[]
            for slip in (2,4):
                r=self.run_one('recent',3,slip);rows.append(r)
                if r['assessment']['decision']=='execution_error':break
            atomic(ROOT/'research'/self.result_name,[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows])

if __name__=='__main__':
    cycle=GapCycle()
    try:cycle.run()
    except Exception as exc:
        cycle.lifecycle.update('failed',str(exc),None);raise
    else:cycle.lifecycle.update('reviewing','Gap-fade finite native tests persisted and ACKed; inspect context and trade ledgers',None)
