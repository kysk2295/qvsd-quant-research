from .rsi_cycle import RsiCycle
from .core import ROOT,atomic,ProcessLock

class ClockDiagnostic(RsiCycle):
    strategy='CodexBollingerClock';parameter='BandLength';bars_value=1;rth_bars=390;requires_eth=False
    manifest_name='execution-clock-manifest.json';folder_name='execution-clock';result_name='execution-clock-results.json';id_prefix='clock-diagnostic-';batch='execution-clock-diagnostic-v1'
    def validate_native(self,doc):
        assert len([x for x in doc['output'] if x.startswith('CLOCK_EXEC|')])==8
        assert len([x for x in doc['output'] if x.startswith('CLOCK_TRADE|')])==4

if __name__=='__main__':
    c=ClockDiagnostic()
    try:
        with ProcessLock(c.folder/'cycle.lock'):
            r=c.run_one('recent',20,2)
            atomic(ROOT/'research'/c.result_name,[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')}])
            assert r['assessment']['decision']!='execution_error'
    except Exception as e:c.lifecycle.update('failed',str(e),None);raise
    c.lifecycle.update('reviewing','Clock diagnostic complete; comparing raw simulated timestamps to original ledger and data',None)
