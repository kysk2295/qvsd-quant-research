"""Bounded intake state. Finite downloader lives in future_data_collector; no scheduler."""
import json,uuid
from datetime import datetime,time,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .core import ROOT,atomic,file_hash,ProcessLock

class FutureIntake:
    def __init__(self,root=ROOT,download_root=None):
        self.root=Path(root);self.planpath=self.root/'research/bollinger-prospective-plan.json'
        self.plan=json.loads(self.planpath.read_text());self.planhash=file_hash(self.planpath)
        self.folder=self.root/'data/runner/future-data-intake';self.folder.mkdir(parents=True,exist_ok=True);self.path=self.folder/'state.json'
        self.download_root=Path(download_root) if download_root else Path.home()/'Documents/NinjaTrader 8/db/replay/NQ 12-26'
    def initialize(self):
        with ProcessLock(self.folder/'intake.lock'):
            if self.path.exists():return self.load()
            entries={}
            for day in self.plan['evaluation_dates']:
                closed=datetime.combine(datetime.fromisoformat(day).date(),time(16),ZoneInfo('America/New_York')).astimezone(timezone.utc)
                entries[day]=dict(session_close_utc=closed.isoformat(),timezone='America/New_York',expected_rth_minutes=390,submission_budget_consumed=0,status='awaiting_session_close',expected_download_path=str(self.download_root/(day.replace('-','')+'.nrd')))
            state=dict(plan_sha256=self.planhash,entries=entries,max_batch=3,max_total=10,max_per_date=1,download_adapter_implemented=False,scheduled_worker_running=False,actual_download_requests=0)
            atomic(self.path,state);return state
    def load(self):
        state=json.loads(self.path.read_text());assert state['plan_sha256']==self.planhash,'Plan changed;do not silently reuse intake'
        return state
    def available(self,now):
        if now.tzinfo is None:raise ValueError('Timezone-aware current time required')
        state=self.load();ready=[];existing=[]
        for day,entry in sorted(state['entries'].items()):
            if Path(entry['expected_download_path']).exists():existing.append(day);continue
            if entry['submission_budget_consumed']==0 and now>=datetime.fromisoformat(entry['session_close_utc']):ready.append(day)
        return dict(eligible_dates=ready[:state['max_batch']],eligible_backlog=ready,existing_files_requiring_audit=existing,requests_sent=0)
    def claim_batch(self,dates,now):
        # A future caller must persist this BEFORE its one allowed UI/API action.
        with ProcessLock(self.folder/'intake.lock'):
            state=self.load();allowed=self.available(now)['eligible_backlog']
            if not dates or len(dates)>3 or len(set(dates))!=len(dates):raise ValueError('One to three distinct dates required')
            if not set(dates)<=set(allowed):raise ValueError('Not closed,already reserved,or file already exists')
            if sum(e['submission_budget_consumed'] for e in state['entries'].values())+len(dates)>10:raise ValueError('Total acquisition budget exhausted')
            token=str(uuid.uuid4())
            for day in dates:state['entries'][day].update(status='reserved_before_external_submission',submission_budget_consumed=1,batch_token=token,reserved_at_utc=now.astimezone(timezone.utc).isoformat())
            atomic(self.path,state);return token
    def record_submission(self,day,token,now):
        with ProcessLock(self.folder/'intake.lock'):
            state=self.load();entry=state['entries'][day]
            if entry.get('batch_token')!=token or entry['status']!='reserved_before_external_submission':raise ValueError('No unique reserved submission')
            entry.update(status='submitted_awaiting_file',submitted_at_utc=now.astimezone(timezone.utc).isoformat());state['actual_download_requests']+=1;atomic(self.path,state)
    def record_failure(self,day,reason):
        with ProcessLock(self.folder/'intake.lock'):
            state=self.load();entry=state['entries'][day]
            if entry['submission_budget_consumed']!=1:raise ValueError('No attempted/reserved date')
            entry.update(status='failed_or_uncertain_no_retry',reason=reason,resume='Inspect existingrequest/file after externalstatechange;do not resubmit thisdate');atomic(self.path,state)
    def record_quality(self,day,audit_path):
        with ProcessLock(self.folder/'intake.lock'):
            state=self.load();entry=state['entries'][day];audit=json.loads(Path(audit_path).read_text())
            source=Path(entry['expected_download_path'])
            if audit.get('date')!=day or audit.get('rth_minutes')!=390 or audit.get('integrity_passed') is not True or audit.get('missing_minutes')!=[]:raise ValueError('Complete dated integrity/session audit required')
            if audit.get('source_sha256')!=file_hash(source):raise ValueError('Source changed or audit mismatch')
            entry.update(status='quality_passed',source_sha256=audit['source_sha256'],audit_path=str(audit_path),audit_sha256=file_hash(audit_path));atomic(self.path,state)

if __name__=='__main__':
    intake=FutureIntake();state=intake.initialize();now=datetime.now(timezone.utc);ready=intake.available(now)
    report=dict(checked_at_utc=now.isoformat(),state_path=str(intake.path),plan_sha256=intake.planhash,entries=state['entries'],readiness=ready,actual_download_requests=state['actual_download_requests'],download_adapter_implemented=False,automatic_collection_running=False,quality_tooling='Existing strictNRDdecoder/Lastformatter reusable;futuredate adapter notwired. Qualityrecord requires date,390minutes,integrity,missingminutes=[],sourcehash.',resume='Onlyclosed registered sessions;max3distinct dates perbatch;reservebeforeonesubmission;unknownoutcomes blockretry;manualexistingfile auditavoidsduplicatedownload. No performance evaluation beforefixeddecision.')
    atomic(ROOT/'research/future-data-intake-readiness.json',report);print(json.dumps(dict(ready=ready,actual_download_requests=state['actual_download_requests'],prepared_dates=len(state['entries']),automatic_collection_running=False)))
