"""Two linked RSI data-repair tests followed by one finite channel candidate."""
import argparse,json
from .rsi_cycle import RsiCycle
from .core import ROOT,ProcessLock,atomic,file_hash

class ChannelCycle(RsiCycle):
    strategy='CodexChannelBreakout'
    manifest_name='channel-breakout-manifest.json'
    folder_name='channel-cycle'
    result_name='channel-breakout-results.json'
    id_prefix='channel-'
    batch='channel-breakout-v1'
    parameter='ChannelLength'
    levels=(5,20)
    requires_eth=False

class RepairCycle(RsiCycle):
    manifest_name='rsi-repair-manifest-v2.json'
    folder_name='rsi-repair-v2'
    result_name='rsi-repair-results-v2.json'
    id_prefix='rsi-repair-v2-'
    batch='rsi-repair-v2'
    coverage_report_name='rsi-eth-coverage-v2.json'
    def lineage(self,request,data_hash):
        super().lineage(request,data_hash)
        original=json.loads((ROOT/'data/runner/rsi-cycle/state.json').read_text())
        parents=[r for r in original['experiments'].values() if r['phase']=='recent' and r['request']['slippageTicks']==request['slippageTicks']]
        assert len(parents)==1
        parent=parents[0]
        assert parent['ack'] and parent['source_hash']==self.sh and parent['data_hash']!=data_hash
        old=parent['request'].copy();new=request.copy();old.pop('from');new.pop('from')
        assert old==new,'Only history start and dataset may change in repair'
        assert request['from']<parent['request']['from']
        report=ROOT/'research'/self.coverage_report_name
        assert json.loads(report.read_text())['complete']
        # Resolved execution metadata supplements, but does not mutate, the frozen research manifest.
        self.manifest['quality_correction']=dict(reason='Repair158 missing scheduled5minute intervals and initial indicator warmup; identical trading rules/evaluation dates',
            previous_run_id=parent['run_id'],previous_key=parent['key'],previous_data_hash=parent['data_hash'],
            new_data_hash=data_hash,evidence_path=str(report),evidence_sha256=file_hash(report),original_request=parent['request'])
        return [parent['key']]
    def run(self):
        with ProcessLock(self.folder/'cycle.lock'):
            rows=[self.run_one('recent',2,slip) for slip in (2,4)]
            atomic(ROOT/'research'/self.result_name,[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','supersedes','quality_correction','ack')} for r in rows])
            assert all(not r['assessment']['data_coverage']['warmup_affected_dates'] for r in rows),'Native indicator warmup still incomplete'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=['repair','channel']);args=parser.parse_args()
    cycle=RepairCycle() if args.kind=='repair' else ChannelCycle()
    try:cycle.run()
    except Exception as exc:
        cycle.lifecycle.update('failed',str(exc),None);raise
    else:cycle.lifecycle.update('idle',args.kind+' finite batch complete; all result ACKs persisted; no background research running',None)

if __name__=='__main__':main()
