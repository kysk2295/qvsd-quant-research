"""Four finite OFI tests with two predeclared chronological exploratory segments."""
import json
from .rsi_cycle import RsiCycle
from .core import ROOT,ProcessLock,atomic,file_hash

class OfiCycle(RsiCycle):
    strategy='CodexQuoteOfi'
    parameter='OfiThreshold'
    bars_value=1
    rth_bars=390
    requires_eth=False
    coverage_report_name='ofi-signal-coverage.json'
    def __init__(self,segment):
        self.manifest_name=f'ofi-{segment}-manifest.json';self.folder_name=f'ofi-{segment}'
        self.result_name=f'ofi-{segment}-results.json';self.id_prefix=f'ofi-{segment}-';self.batch=f'ofi-{segment}-v1'
        super().__init__()
    def validate_native(self,doc):
        coverage=json.loads((ROOT/'research'/self.coverage_report_name).read_text())
        assert file_hash(coverage['path'])==coverage['sha256']
        assert f"FEATURE_HASH {coverage['sha256']} rows={coverage['rows']}" in doc['output']
        assert not any('missing_feature=' in x for x in doc['output'] if x.startswith('COUNTS '))
    def run(self):
        with ProcessLock(self.folder/'cycle.lock'):
            rows=[]
            for slip in (2,4):
                r=self.run_one('recent',10,slip);rows.append(r)
                if r['assessment']['decision']=='execution_error':break
            atomic(ROOT/'research'/self.result_name,[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows])
            if any(r['assessment']['decision']=='execution_error' for r in rows):raise RuntimeError('OFI execution verification failed; no next segment')

if __name__=='__main__':
    for segment in ('early','late'):
        cycle=OfiCycle(segment)
        try:cycle.run()
        except Exception as exc:
            cycle.lifecycle.update('failed',str(exc),None);raise
    cycle.lifecycle.update('reviewing','Four OFI native tests persisted with ACKs; auditing feature timestamps and native fill ledgers',None)
