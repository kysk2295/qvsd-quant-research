"""Six-run preregistered NQ RSI2 adaptation, native Backtest account only."""
import json,hashlib,time
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from .core import ROOT,Queue,ProcessLock,atomic,canonical,file_hash,dataset_hash
from .adapter import Bridge
from .assessment import assess,ledger_evidence,additional_slippage_evidence
from .research_protocol import validate_manifest,enqueue_extension
from .research_lifecycle import Lifecycle
from .cafe_extension import check_prior_records
from dashboard.reporter import post,emit
from dashboard.server import validate_run

class RsiCycle:
    strategy='CodexRsiPullback'
    manifest_name='rsi-pullback-manifest.json'
    folder_name='rsi-cycle'
    result_name='rsi-pullback-results.json'
    id_prefix='rsi-'
    batch='rsi-pullback-v1'
    parameter='EntryLevel'
    levels=(5,2)
    requires_eth=True
    coverage_report_name=None
    bars_value=5
    rth_bars=78
    def validate_native(self,doc):
        pass
    def lineage(self,request,data_hash):
        return check_prior_records(self.state['experiments'].values(),request,self.manifest.get('quality_correction'),data_hash,self.sh)
    def __init__(self):
        self.folder=ROOT/'data/runner'/self.folder_name;self.folder.mkdir(exist_ok=True)
        self.manifest=json.loads((ROOT/'research'/self.manifest_name).read_text())
        self.mh=validate_manifest(self.manifest)
        self.source=ROOT/'native'/(self.strategy+'.cs');self.sh=file_hash(self.source)
        assert self.sh==file_hash(Path.home()/'Documents/NinjaTrader 8/bin/Custom/Strategies'/(self.strategy+'.cs'))
        self.bridge=Bridge();self.q=Queue();self.lifecycle=Lifecycle()
        self.config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
        self.statepath=self.folder/'state.json'
        self.state=json.loads(self.statepath.read_text()) if self.statepath.exists() else dict(experiments={},selected=None)
    def save(self):atomic(self.statepath,self.state)
    def run_one(self,phase,level,slip):
        dates=self.manifest['data_requirements'][phase];compact={d.replace('-','') for d in dates}
        recent=phase=='recent';fee=10 if slip==4 else 5
        if recent:
            audit=json.loads((ROOT/'research/recent-tick-audit-20261025.json').read_text())
            valid={s['date'] for row in audit for s in row['sessions'] if s['minutes']==390 and not s['missingMinutes']}
            assert set(dates)<=valid,'Recent full tick coverage missing'
        db=Path.home()/'Documents/NinjaTrader 8/db'
        # NinjaTrader may prefetch bars before the requested date. Snapshot all local instrument
        # files, rather than omitting earlier prefetch files from the pre-execution fingerprint.
        start=self.manifest['data_requirements'].get('recent_request_from','2026-10-11') if recent else '2026-09-28'
        end=self.manifest['data_requirements'].get('recent_request_to','2026-10-23') if recent else '2026-10-07'
        files=sorted(p for kind in (('minute','tick') if recent else ('minute',)) for p in (db/kind/'NQ 12-26').glob('*.ncd'))
        assert files;dh=dataset_hash(files)
        req=dict(strategy=self.strategy,instrument='NQ DEC26',barsPeriod={'type':'Minute','value':self.bars_value},
            inputs={self.parameter:level,'FirstDate':int(min(compact)),'LastDate':int(max(compact))},
            tickReplay=False,includeCommission=False,includeTradeHistory=True,slippageTicks=slip,
            fillResolution='High' if recent else 'Standard',breakAtEod=True,
            **{'from':start,'to':end})
        if recent:req.update(fillResolutionType='Tick',fillResolutionValue=1)
        key=hashlib.sha256(canonical([req,dh,self.sh,self.mh]).encode()).hexdigest()
        if key in self.state['experiments']:
            old=self.state['experiments'][key]
            if old.get('ack'):return old
            raise RuntimeError('Uncertain prior submission or ACK; inspect without resubmitting')
        lineage=self.lineage(req,dh)
        coverage_report=None
        if self.coverage_report_name:
            coverage_report=json.loads((ROOT/'research'/self.coverage_report_name).read_text())
            assert coverage_report['complete'],'Required ETH coverage is not complete'
        health=self.bridge.call('GET','/health');jobs=self.bridge.call('GET','/backtests')
        assert not health.get('anyLive') and not health.get('anyNonSim') and not health.get('standingModal')
        assert not any(j['state'] in ('queued','running') for j in jobs)
        if self.q.control('mode')=='stopped':raise RuntimeError('User stop')
        r=dict(key=key,request=req,source_hash=self.sh,data_hash=dh,data_hash_scope='All local NQ minute files, and tick files for High fills, including native prefetch',manifest_hash=self.mh,started=time.time(),state='submitting',phase=phase,supersedes=lineage,quality_correction=self.manifest.get('quality_correction'))
        self.state['experiments'][key]=r;self.save()
        self.lifecycle.update('running',self.strategy+' '+phase+' native test',current_run=self.id_prefix+key[:24])
        r['native_id']=self.bridge.call('POST','/backtest',req)['id'];self.save();deadline=time.time()+180
        while True:
            doc=self.bridge.call('GET','/backtest/'+r['native_id'])
            if doc['state'] not in ('running','queued'):break
            if self.q.control('mode')=='stopped' or time.time()>deadline:
                self.bridge.call('DELETE','/backtest/'+r['native_id']);raise RuntimeError('Stopped/deadline')
            time.sleep(1)
        atomic(self.folder/(key+'.native.json'),doc);r['doc']=doc;self.save()
        error=None;data_issue=None;counters={}
        try:
            assert doc['state']=='done' and not doc.get('error'),doc.get('error')
            s=doc['settings'];assert s['fillResolution']==req['fillResolution'] and s['slippageTicks']==slip and s['includeCommission'] is False
            if recent:assert s['fillResolutionType']=='Tick' and s['fillResolutionValue']==1
            assert doc['tickReplay'] is False and len(doc['trades'])==doc['summary']['trades']
            assert not any('ORDER_ERROR' in x for x in doc['output'])
            audits=[x for x in doc['output'] if x.startswith('AUDIT ')]
            if {x.split()[1] for x in audits}!=compact or any(f'bars={self.rth_bars} gap=False' not in x for x in audits):data_issue='Incomplete native RTH audit'
            self.validate_native(doc)
            for t in doc['trades']:
                entry=datetime.fromisoformat(t['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
                assert entry.strftime('%Y%m%d') in compact and t['qty']==1
            for line in doc['output']:
                if line.startswith('COUNTS '):counters[line.split()[1]]={k:int(v) for k,v in (p.split('=') for p in line.split()[2:])}
            if file_hash(self.source)!=self.sh or dataset_hash(files)!=dh:data_issue='Source or data changed during run'
        except Exception as exc:error=str(exc) or 'Native verification failed'
        review=assess(doc.get('trades',[]),fee,0,implementation_error=error,data_issue=data_issue)
        if review['decision']=='further_validation':review.update(decision='deferred',reason='Positive short sample; session coverage, dependence and prospective evidence still insufficient')
        review.pop('minimum_trades',None);review.update(coverage_policy=self.manifest['coverage_policy'],condition_counts=counters,ledger_evidence=ledger_evidence(doc.get('trades',[]),fee))
        review['additional_fill_cost_sensitivity']=[additional_slippage_evidence(doc.get('trades',[]),fee,ticks) for ticks in (2,4)]
        warmup_dates=[d for d,counts in counters.items() if counts.get('indicator_warmup',0)]
        review['data_coverage']=dict(warmup_affected_dates=warmup_dates,requested_rth_sessions=len(dates),
            native_bars_from=doc.get('barsFrom'),native_bars_to=doc.get('barsTo'),warnings=doc.get('warnings'),
            complete_eth_indicator_history_verified=bool(coverage_report) if self.requires_eth else None,
            coverage_evidence=self.coverage_report_name,
            note=('Observed scheduled ETH intervals and required indicator context verified; interval presence does not establish lossless tick completeness.' if coverage_report else 'RTH coverage does not verify full ETH indicator history. Warmup days are not fully entry-eligible sessions.') if self.requires_eth else 'ETH indicator warmup is not required; consult the strategy-specific session/context evidence.')
        for date in dates:review['ledger_evidence']['daily_net'].setdefault(date,0)
        review['next_action']='Review frozen hypothesis; positive/zero samples need broader session evidence; never tune against recent results'
        if warmup_dates:
            review['next_action']='Acquire and audit complete pre-window ETH indicator history including at least200 five-minute warmup bars; freeze a versioned data-coverage repair before reevaluation; retain original metrics and do not retune'
        enqueue_extension(ROOT/'research/evidence-work-queue.json',self.batch+'-'+str(level),review,self.mh)
        status='failed' if error else 'completed'
        equity=[];balance=150000.0
        for trade in sorted(doc.get('trades',[]),key=lambda t:t['exitTime']):
            balance+=trade['pnl']-fee*trade['qty'];equity.append(dict(date=trade['exitTime'],value=balance))
        run=dict(id=self.id_prefix+key[:24],strategy=self.strategy,symbol='NQ',worker='windows-candidate-research',source=self.manifest['source'],batch=self.batch,
            dataset=phase+' NQ DEC26',data_hash=dh,status=status,phase=phase,progress=100,reason=review['reason'],cost=f'{slip} ticks + ${fee} assumed roundtrip',
            params=dict(inputs=req['inputs'],assessment=review,source_hash=self.sh,manifest_hash=self.mh,native_trade_ledger=doc.get('trades',[]),supersedes=lineage,quality_correction=self.manifest.get('quality_correction')),metrics=dict(net=review['net_after_assumed_fee'],trades=review['trade_count']),equity=equity,
            started_at=r['started'],completed_at=time.time(),evidence='research/'+self.result_name+'; complete native ledgers persisted locally')
        validate_run(run);emit(run,self.q.telemetry);ack=post(self.config['url'],'/api/runs',run,self.config['token']);assert ack.get('ok') is True
        snap=self.q.telemetry/(hashlib.sha256(run['id'].encode()).hexdigest()+'.json');self.q.control('ack:'+snap.name,file_hash(snap))
        r.update(state='terminal',assessment=review,run_id=run['id'],ack=True);self.save()
        print(canonical(dict(phase=phase,level=level,slip=slip,net=review['net_after_assumed_fee'],trades=review['trade_count'],decision=review['decision'],ack=True)),flush=True)
        return r
    def run(self):
        with ProcessLock(self.folder/'cycle.lock'):
            dev=[self.run_one('development',level,slip) for level in self.levels for slip in (2,4)]
            valid=[r for r in dev if r['request']['slippageTicks']==4 and r['assessment']['decision']!='execution_error' and r['assessment']['reason']!='Incomplete native RTH audit']
            if not valid:raise RuntimeError('No valid development result; do not proceed')
            selected=max(valid,key=lambda r:r['assessment']['net_after_assumed_fee'])['request']['inputs'][self.parameter]
            if self.state['selected'] is None:self.state['selected']=dict(level=selected,frozen_at=time.time());self.save()
            assert selected==self.state['selected']['level']
            recent=[self.run_one('recent',selected,slip) for slip in (2,4)]
            atomic(ROOT/'research'/self.result_name,[dict({k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','phase','assessment','ack')},assessment_history=r.get('assessment_history',[])) for r in dev+recent])

if __name__=='__main__':
    cycle=RsiCycle()
    try:cycle.run()
    except Exception as exc:
        cycle.lifecycle.update('failed',str(exc),None);raise
    else:cycle.lifecycle.update('idle','Finite RSI2 batch complete; all ACKs persisted; no background research running',None)
