"""One frozen configuration, two native cost tests, no optimization."""
from .rsi_cycle import RsiCycle
from .core import ROOT,ProcessLock,atomic

class MomentumCycle(RsiCycle):
    strategy='CodexMovingMomentum'
    manifest_name='moving-momentum-manifest.json'
    folder_name='moving-momentum'
    result_name='moving-momentum-results.json'
    id_prefix='momentum-'
    batch='moving-momentum-v1'
    parameter='SetupMaxBars'
    levels=(6,)
    coverage_report_name='moving-momentum-coverage.json'
    def run(self):
        with ProcessLock(self.folder/'cycle.lock'):
            rows=[self.run_one('recent',6,slip) for slip in (2,4)]
            atomic(ROOT/'research'/self.result_name,[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows])

if __name__=='__main__':
    cycle=MomentumCycle()
    try:cycle.run()
    except Exception as exc:
        cycle.lifecycle.update('failed',str(exc),None);raise
    else:cycle.lifecycle.update('reviewing','Two Moving Momentum native tests completed and ACKed; auditing signal and fill ledgers',None)
