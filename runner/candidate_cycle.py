"""Finite, resumable native candidate replenishment. No self-invocation or live orders."""
import hashlib,json,time,subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from .core import ROOT,Queue,ProcessLock,atomic,canonical,file_hash,dataset_hash
from .adapter import Bridge
from dashboard.reporter import post,emit
from dashboard.server import validate_run
from .assessment import assess
from .research_protocol import validate_manifest,enqueue_extension

FOLDER=ROOT/'data/runner/doji-cycle'
BACKLOG=ROOT/'research/candidate-backlog.json'
DATES={'development':{'20260929','20260930','20261001','20261002','20261005','20261006'},
       'recent':{'20261019','20261020','20261021','20261022'}}

def classify(doc,phase,fee):
    if doc.get('state')!='done' or doc.get('error'):return {'classification':'implementation_error','net':0,'trades':0,'reason':str(doc.get('error'))}
    settings=doc.get('settings',{})
    expected='High' if phase=='recent' else 'Standard'
    if settings.get('fillResolution')!=expected or settings.get('includeCommission') is not False or doc.get('tickReplay') is not False:
        raise ValueError('Effective fill settings differ from plan')
    if phase=='recent' and (settings.get('fillResolutionType')!='Tick' or settings.get('fillResolutionValue')!=1):raise ValueError('Tick fill resolution not applied')
    output=doc.get('output') or []
    audits=[x for x in output if x.startswith('AUDIT ')]
    if any('ORDER_ERROR' in x for x in output):raise ValueError('Native order error')
    if {x.split()[1] for x in audits}!=DATES[phase] or any('bars=390 gap=False' not in x for x in audits):
        return dict(classification='data_insufficient',net=0,trades=0,reason='Expected full session audits missing')
    trades=doc['trades'];assert len(trades)==doc['summary']['trades']
    for t in trades:
        entry=datetime.fromisoformat(t['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
        assert entry.strftime('%Y%m%d') in DATES[phase] and t['qty']==1
    pnl=[t['pnl']-fee*t['qty'] for t in trades];net=sum(pnl)
    signals=sum(int(x.split(' signals=')[1].split()[0]) for x in audits)
    rejects=sum(int(x.split(' rejected=')[1].split()[0]) for x in audits)
    losses=-sum(p for p in pnl if p<0);gains=sum(p for p in pnl if p>0)
    pf=gains/losses if losses else None
    classification=('condition_mismatch' if signals else 'no_signal') if not trades else 'performance_rejected' if net<=0 else 'sample_insufficient' if len(trades)<(30 if phase=='development' else 20) else 'research_positive'
    return dict(classification=classification,net=net,trades=len(trades),signals=signals,conditionRejected=rejects,
                profitFactor=pf,maxWinShare=max(pnl)/net if pnl and net>0 else None,
                reason='Native diagnostic only; previously observed dates; no independent OOS')

class Cycle:
    def __init__(self):
        self.bridge=Bridge();self.q=Queue();FOLDER.mkdir(parents=True,exist_ok=True)
        self.config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text(encoding='utf-8'))
        self.statepath=FOLDER/'state.json'
        self.state=json.loads(self.statepath.read_text(encoding='utf-8')) if self.statepath.exists() else {'experiments':{},'selected':{},'next_action':'run first ready candidate'}
        self.source_hash=file_hash(ROOT/'native/CodexDojiResearch.cs')
        installed=Path.home()/'Documents/NinjaTrader 8/bin/Custom/Strategies/CodexDojiResearch.cs'
        assert file_hash(installed)==self.source_hash,'Installed strategy differs'
        self.commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    def save(self):atomic(self.statepath,self.state)
    def publish(self,key,record,status):
        result=record.get('result',{});req=record['request'];doc=record.get('doc',{})
        assessment=assess(doc.get('trades',[]),record['fee'],20 if record['phase']=='recent' else 30,
                          implementation_error=result.get('reason') if result.get('classification')=='implementation_error' else None,
                          data_issue=result.get('reason') if result.get('classification')=='data_insufficient' else None,
                          signals=result.get('signals'),condition_rejected=result.get('conditionRejected')) if result else None
        run=dict(id='doji-'+key[:24],strategy='CodexDojiResearch',symbol='NQ',worker='windows-candidate-research',
                 source='Native NT historical engine; cafe motifs with explicit research rules',batch=record['candidate'],
                 dataset=record['phase']+' NQ DEC26 1minute',data_hash=record['data_hash'],code_commit=self.commit,
                 status=status,phase=record['phase']+': '+result.get('classification',record['state']),
                 progress=100 if status in ('rejected','failed','completed') else 25,
                 reason=result.get('reason','Finite candidate batch running'),
                 cost=str(req['slippageTicks'])+' ticks + assumed $'+str(record['fee'])+' round trip',
                 params=dict(inputs=req['inputs'],settings=doc.get('settings'),classification=result.get('classification'),
                             source_hash=self.source_hash,independent_oos=False,strategy_replay=False,assessment=assessment),
                 metrics={k:result[k] for k in ('net','trades','signals','conditionRejected','profitFactor') if k in result},equity=[],
                 started_at=record['started'],completed_at=record.get('finished'),
                 evidence='docs/doji-batch-2026-10-25.md; full native response persisted locally before ACK')
        validate_run(run);emit(run,self.q.telemetry)
        response=post(self.config['url'],'/api/runs',run,self.config['token'])
        if response.get('ok') is not True:raise RuntimeError('Dashboard ACK missing')
        snap=self.q.telemetry/(hashlib.sha256(run['id'].encode()).hexdigest()+'.json')
        self.q.control('ack:'+snap.name,file_hash(snap));record['ack']=status;self.save()
        post(self.config['url'],'/api/heartbeat',dict(id='windows-candidate-research',label='Windows NQ candidate research',phase='research',current_run=run['id'] if status=='running' else None,message=run['phase']),self.config['token'])
    def run_one(self,candidate,phase,inputs,slip):
        if self.q.control('mode')=='stopped':raise RuntimeError('User stop active')
        folder=Path.home()/'Documents/NinjaTrader 8/db'
        # Hash only the relevant date files; canonical request + file hashes prevent duplicate reruns.
        prefixes=('202609','2026100') if phase=='development' else ('20261019','20261020','20261021','20261022','20261023')
        files=sorted(p for kind in (('minute',) if phase=='development' else ('minute','tick')) for p in (folder/kind/'NQ 12-26').glob('*.ncd') if p.name.startswith(prefixes))
        assert files,'No historical files'
        data_hash=dataset_hash(files)
        request=dict(strategy='CodexDojiResearch',instrument='NQ DEC26',barsPeriod={'type':'Minute','value':1},
                     inputs={**inputs,'FirstDate':int(min(DATES[phase])),'LastDate':int(max(DATES[phase]))},
                     tickReplay=False,includeCommission=False,includeTradeHistory=True,slippageTicks=slip,
                     fillResolution='High' if phase=='recent' else 'Standard',breakAtEod=True)
        request.update({'from':'2026-09-28','to':'2026-10-07'} if phase=='development' else {'from':'2026-10-19','to':'2026-10-23'})
        if phase=='recent':request.update(fillResolutionType='Tick',fillResolutionValue=1)
        key=hashlib.sha256(canonical(dict(request=request,source=self.source_hash,data=data_hash)).encode()).hexdigest()
        record=self.state['experiments'].get(key)
        if record and record['state']=='terminal':
            if record.get('ack')!=record['dashboard_status']:self.publish(key,record,record['dashboard_status'])
            return record
        if record:raise RuntimeError('Uncertain/unfinished native submission; inspect state before resuming, never resubmit')
        manifest_path=ROOT/'research/manifests'/(candidate+'.json')
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest_hash=validate_manifest(manifest)
        health=self.bridge.call('GET','/health');jobs=self.bridge.call('GET','/backtests')
        if health.get('anyLive') or health.get('anyNonSim') or health.get('standingModal') or any(j['state'] in ('running','queued') for j in jobs):raise RuntimeError('Native engine not exclusively available')
        record=dict(candidate=candidate,phase=phase,request=request,data_hash=data_hash,source_hash=self.source_hash,
                    fee=5 if slip==2 else 10,state='prepared',started=time.time(),manifest_hash=manifest_hash)
        self.state['experiments'][key]=record;self.save();self.publish(key,record,'running')
        record['state']='submitting';record['instance']=health['startedAt'];self.save()
        reply=self.bridge.call('POST','/backtest',request)
        record['native_id']=reply['id'];record['state']='running';self.save()
        deadline=time.time()+180
        while True:
            if self.q.control('mode')=='stopped' or time.time()>deadline:
                self.bridge.call('DELETE','/backtest/'+record['native_id']);raise RuntimeError('Stopped or native deadline exceeded')
            if self.bridge.call('GET','/health')['startedAt']!=record['instance']:raise RuntimeError('Native instance changed; submission uncertain')
            doc=self.bridge.call('GET','/backtest/'+record['native_id'])
            if doc['state'] not in ('queued','running'):break
            time.sleep(1)
        atomic(FOLDER/(key+'.native.json'),doc)
        record['doc']=doc
        try:record['result']=classify(doc,phase,record['fee'])
        except Exception as exc:record['result']=dict(classification='implementation_error',reason=str(exc),net=0,trades=0)
        if file_hash(ROOT/'native/CodexDojiResearch.cs')!=self.source_hash or dataset_hash(files)!=data_hash:
            record['result']=dict(classification='data_insufficient',reason='Source/dataset changed during execution',net=0,trades=0)
        record['finished']=time.time();record['state']='terminal'
        classification=record['result']['classification']
        record['dashboard_status']='failed' if classification=='implementation_error' else 'completed' if classification in ('research_positive','sample_insufficient') else 'rejected'
        self.save();self.publish(key,record,record['dashboard_status'])
        review=assess(doc.get('trades',[]),record['fee'],20 if phase=='recent' else 30,
                      signals=record['result'].get('signals'),condition_rejected=record['result'].get('conditionRejected'))
        enqueue_extension(ROOT/'research/evidence-work-queue.json',candidate,review,manifest_hash)
        print(canonical(dict(candidate=candidate,phase=phase,inputs=inputs,slip=slip,result=record['result'],ack=record['ack'])),flush=True)
        return record
    def run(self):
        with ProcessLock(FOLDER/'cycle.lock'):
            backlog=json.loads(BACKLOG.read_text(encoding='utf-8'))
            options={'doji-bearish-v1':[{'SessionWindow':0,'TargetRatio':.6},{'SessionWindow':0,'TargetRatio':1.0}],
                     'doji-opening-window-v1':[{'SessionWindow':30,'TargetRatio':.6},{'SessionWindow':60,'TargetRatio':.6}]}
            for candidate in sorted(backlog['candidates'],key=lambda c:c['priority']):
                cid=candidate['id']
                if cid not in options or candidate['status'] not in ('ready','running'):continue
                candidate['status']='running';candidate['next_action']='finite development then frozen recent';atomic(BACKLOG,backlog)
                development=[]
                for inputs in options[cid]:
                    for slip in (2,4):development.append(self.run_one(cid,'development',inputs,slip))
                stress=[r for r in development if r['request']['slippageTicks']==4 and r['result']['classification'] not in ('implementation_error','data_insufficient')]
                if not stress:
                    candidate.update(status='blocked',next_action='resolve implementation/data evidence, no recent tuning');atomic(BACKLOG,backlog);continue
                best=max(stress,key=lambda r:r['result']['net'])
                selected={k:best['request']['inputs'][k] for k in ('SessionWindow','TargetRatio')}
                self.state['selected'][cid]=dict(inputs=selected,selection='development stress net; baseline tie',frozen_at=time.time());self.save()
                recent=[self.run_one(cid,'recent',selected,slip) for slip in (2,4)]
                candidate.update(status='evaluated',result=[r['result'] for r in recent],next_action='review gates; no automatic risk increase; collect prospective data if warranted')
                atomic(BACKLOG,backlog)
            next_candidates=[c for c in backlog['candidates'] if c['status'] in ('ready','research_needed')]
            action=next_candidates[0]['next_action'] if next_candidates else 'Source additional genuinely new explicit strategies; do not repeat completed fingerprints'
            backlog['next_action']=action;self.state['next_action']=action;atomic(BACKLOG,backlog);self.save()
            print(canonical(dict(next_action=action,finished_experiments=len(self.state['experiments']))),flush=True)

if __name__=='__main__':Cycle().run()
