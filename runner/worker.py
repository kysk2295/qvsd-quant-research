import json
import os
import subprocess
import sys
import time
from pathlib import Path
from .core import ROOT, Queue, ProcessLock, atomic, canonical, file_hash
from .adapter import Bridge, verify_files, native_result

class Worker:
    def __init__(self,q,bridge=None):
        self.q=q;self.bridge=bridge or Bridge();self.child=None;self.last_telemetry=0

    def finish(self,jid,result):
        atomic(self.q.folder/(jid+'.result.json'),result)
        self.q.update(jid,status='rejected' if result.get('rejected') else 'completed',
                      phase='검증 계산 완료 · 채택과 별개',progress=100,result=canonical(result),reason=result['reason'])
        if result.get('coverage_invalid'):
            spec=json.loads(self.q.get(jid)['spec'])
            self.q.control('coverage-block:'+spec['data_hash'],'Native loaded/requested coverage mismatch')
            for other in self.q.rows():
                other_spec=json.loads(other['spec'])
                if (other['status']=='queued' and other_spec['engine']=='nt' and
                    other_spec['data_hash']==spec['data_hash'] and not other_spec['params'].get('expected_bars')):
                    self.q.block(other['id'],'Earlier native case failed coverage; further comparison blocked')

    def cancel(self,row,reason):
        try:
            h=self.bridge.call('GET','/health')
            if h.get('startedAt')!=row['nt_instance']: raise ValueError('NT instance changed')
            self.bridge.call('DELETE','/backtest/'+row['nt_id'])
            jobs=self.bridge.call('GET','/backtests')
            if any(j.get('state') in ('queued','running') for j in jobs): raise ValueError('Active NT job remains')
            self.q.update(row['id'],status='failed',phase='종료',reason=reason)
        except Exception as exc:
            self.q.uncertain(row['id'],reason+'; cancellation unconfirmed: '+type(exc).__name__)

    def tick(self):
        active=[r for r in self.q.rows() if r['status']=='running']
        if active:
            self.poll(active[0]);return
        jid=self.q.claim()
        if jid: self.start(jid)

    def start(self,jid):
        row=self.q.get(jid);s=json.loads(row['spec'])
        if s['engine']=='blocked':
            self.q.block(jid,s.get('blocked_reason','Required data unavailable'));return
        if (s['engine']=='nt' and self.q.control('coverage-block:'+s['data_hash']) and
            not s['params'].get('expected_bars') and not s['request'].get('explicitBars')):
            self.q.block(jid,'Known native coverage mismatch; requires repaired data or explicit observed-window reproduction');return
        try: verify_files(s)
        except Exception as exc:
            self.q.block(jid,str(exc));return
        if s['engine']=='python':
            atomic(self.q.folder/(jid+'.spec.json'),s)
            self.q.update(jid,phase='python-running',progress=40,deadline=time.time()+s['timeout_s'])
            log=(self.q.folder/(jid+'.log')).open('ab')
            try:
                self.child=subprocess.Popen([sys.executable,'-m','runner.adapter',str(self.q.folder/(jid+'.spec.json')),
                                             str(self.q.folder/(jid+'.output.json'))],cwd=ROOT,stdout=log,stderr=log,
                                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            except Exception as exc:
                self.q.update(jid,status='failed',reason='Python launch: '+type(exc).__name__)
            finally:log.close()
            return
        try:
            h=self.bridge.call('GET','/health');jobs=self.bridge.call('GET','/backtests')
            if not h.get('ok') or h.get('anyLive') or h.get('anyNonSim') or h.get('standingModal'):
                raise ValueError('Research environment not ready')
            if any(j.get('state') in ('queued','running') for j in jobs): raise ValueError('Another NT job active')
        except Exception as exc:
            self.q.block(jid,'Native preflight: '+str(exc)[:180],retry=True);return
        # Write-ahead intent. A lost response must NEVER cause automatic resubmission.
        self.q.update(jid,phase='submitting',progress=20,nt_instance=h['startedAt'],deadline=time.time()+s['timeout_s'])
        try:
            response=self.bridge.call('POST','/backtest',s['request'])
            native_id=str(response['id'])
            if not native_id.isalnum(): raise ValueError('Unexpected native ID')
            self.q.update(jid,nt_id=native_id,phase='native-running',progress=50)
        except Exception as exc:
            self.q.uncertain(jid,'Submission outcome unknown: '+type(exc).__name__)

    def poll(self,row):
        jid=row['id'];s=json.loads(row['spec']);stopped=self.q.control('mode')=='stopped'
        if s['engine']=='nt':
            if not row['nt_id']:
                if row['phase']=='preflight':
                    self.q.update(jid,status='queued',phase='복구 · 제출 전');return
                self.q.uncertain(jid,'Restart during submission; inspect NT before manual resolution');return
            if stopped or time.time()>row['deadline']:
                self.cancel(row,'Stopped by user' if stopped else 'Native deadline exceeded');return
            try:
                h=self.bridge.call('GET','/health')
                if h.get('startedAt')!=row['nt_instance']:
                    self.q.uncertain(jid,'NT restarted; native job identity no longer reliable');return
                doc=self.bridge.call('GET','/backtest/'+row['nt_id'])
            except Exception as exc:
                self.q.update(jid,phase='native-poll-wait',reason='Polling unavailable: '+type(exc).__name__);return
            state=doc.get('state')
            if state=='done':
                # Persist sanitized audit, never account details or raw market data in telemetry.
                atomic(self.q.folder/(jid+'.native.json'),{k:doc.get(k) for k in
                      ('state','settings','from','to','timeZone','explicitBars','barsFrom','barsTo','warnings','summary','trades','equity')})
                try:
                    verify_files(s)
                    self.finish(jid,native_result(doc,s))
                except Exception as exc:self.q.update(jid,status='failed',phase='결과 검증 실패',reason=str(exc)[:240])
            elif state in ('error','timeout','cancelled'):
                self.q.update(jid,status='failed',phase='NT 계산 실패',reason=str(doc.get('error',state))[:240])
            elif state not in ('queued','running'):
                self.q.uncertain(jid,'Unexpected native state '+str(state))
            return
        output=self.q.folder/(jid+'.output.json')
        if output.exists():
            if self.child and self.child.poll() is None: return
            self.finish(jid,json.loads(output.read_text(encoding='utf-8')));self.child=None;return
        if self.child is None:
            self.q.update(jid,status='blocked',phase='복구 확인 필요',reason='Python process interrupted; not rerun automatically');return
        if stopped or time.time()>row['deadline']:
            self.child.kill();self.child.wait(timeout=5);self.child=None
            self.q.update(jid,status='failed',phase='종료',reason='Python stopped or deadline exceeded');return
        rc=self.child.poll()
        if rc is not None:
            self.q.update(jid,status='failed',phase='Python 실패',reason='Child exit '+str(rc)+'; see local job log');self.child=None

    def telemetry(self):
        now=time.time()
        if now-self.last_telemetry<15:return
        self.last_telemetry=now
        rows=self.q.rows();active=next((r['id'] for r in rows if r['status']=='running'),None)
        phase='running' if active else ('idle' if self.q.control('mode')=='running' else self.q.control('mode'))
        self.q.health(phase,active)
        # Dedicated worker heartbeat, independent of the old snapshot reporter.
        config=ROOT.parent/'qvsd-dashboard-agent'/'.dashboard-worker.json'
        try:
            from urllib.request import Request, urlopen
            def post(url,path,payload,token):
                req=Request(url.rstrip('/')+path,canonical(payload).encode(),
                            {'Content-Type':'application/json','Authorization':'Bearer '+token},method='POST')
                with urlopen(req,timeout=5) as response:return json.load(response)
            c=json.loads(config.read_text(encoding='utf-8'))
            if not c['url'].startswith('https://'):raise ValueError('HTTPS required')
            for row in rows:
                self.q.emit(row['id'])
            post(c['url'],'/api/heartbeat',dict(id='windows-experiment-runner',label='Windows · NQ 실험 실행기',
                 phase=phase,current_run=active,message='대기열 '+str(sum(r['status']=='queued' for r in rows))
                 +'건 · '+('새 실험 대기' if not active else '계산 중')),c['token'])
            self.q.control('heartbeat_ack',str(time.time()))
            uploaded=0
            for path in sorted(self.q.telemetry.glob('*.json')):
                sha=file_hash(path);key='ack:'+path.name
                if self.q.control(key)==sha:continue
                response=post(c['url'],'/api/runs',json.loads(path.read_text(encoding='utf-8')),c['token'])
                if response.get('ok') is not True:raise ValueError('Snapshot not acknowledged')
                self.q.control(key,sha);uploaded+=1
                if uploaded>=4:break
        except Exception as exc:self.q.control('heartbeat_error',type(exc).__name__)

    def run(self,once=False):
        with ProcessLock(self.q.folder/'runner.lock'):
            while True:
                self.tick();self.telemetry()
                if once:return
                time.sleep(2 if any(r['status']=='running' for r in self.q.rows()) else 15)
