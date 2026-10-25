"""Two fixed-setting historical extension runs; no parameter selection."""
from .rsi_cycle import RsiCycle
from .core import ROOT, ProcessLock, atomic

class ExtensionCycle(RsiCycle):
    manifest_name='rsi-extension-oct7-9-manifest.json'
    folder_name='rsi-extension-oct7-9'
    result_name='rsi-extension-oct7-9-results.json'
    id_prefix='rsi-oct7-9-'
    batch='rsi-extension-oct7-9'
    coverage_report_name='rsi-extension-oct7-9-coverage.json'
    def run(self):
        with ProcessLock(self.folder/'cycle.lock'):
            rows=[self.run_one('recent',2,slip) for slip in (2,4)]
            atomic(ROOT/'research'/self.result_name,[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows])
            assert all(not r['assessment']['data_coverage']['warmup_affected_dates'] for r in rows)

if __name__=='__main__':
    cycle=ExtensionCycle()
    try:cycle.run()
    except Exception as exc:
        cycle.lifecycle.update('failed',str(exc),None)
        raise
    else:cycle.lifecycle.update('idle','Two fixed RSI extension native tests completed and ACKed; Replay pending simulation arming',None)
