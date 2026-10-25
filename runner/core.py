import contextlib
import hashlib
import json
import math
import os
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / 'data' / 'runner'
DEFAULT_TELEMETRY = DEFAULT_STATE / 'telemetry'
TERMINAL = {'completed', 'failed', 'rejected', 'blocked'}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def dataset_hash(files):
    return hashlib.sha256(canonical([(Path(p).name, file_hash(p)) for p in sorted(files)]).encode()).hexdigest()

def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(canonical(value), encoding='utf-8')
    os.replace(tmp, path)

def validate(spec):
    if spec.get('symbol') != 'NQ' or spec.get('engine') not in {'python', 'nt', 'blocked'}:
        raise ValueError('Only explicit NQ research engines are allowed')
    for key in ('strategy', 'dataset', 'data_hash', 'code_commit', 'code_hash', 'params', 'cost', 'timeout_s'):
        if key not in spec:
            raise ValueError('Missing ' + key)
    if not 1 <= spec['timeout_s'] <= 600 or not 0 <= spec.get('max_preflight_retries', 1) <= 2:
        raise ValueError('Finite timeout/retry budget required')
    if spec['engine'] == 'nt':
        b = spec['request']
        if b.get('instrument') != 'NQ 12-26' or b.get('strategy') != 'SampleMACrossOver':
            raise ValueError('Native v1 allowlist: reviewed SampleMACrossOver, NQ 12-26 only')
        allowed = {'strategy','instrument','from','to','barsPeriod','inputs','tickReplay','fillResolution',
                   'slippageTicks','includeCommission','fillLimitOnTouch','includeTradeHistory','breakAtEod'}
        if set(b)-allowed or b.get('tickReplay') is not False or b.get('includeTradeHistory') is not True:
            raise ValueError('Unexpected native request')
        if b.get('includeCommission') is not False or b.get('fillResolution') != 'Standard':
            raise ValueError('v1 uses explicit postprocessed assumed commission and Standard fills')
        if b.get('barsPeriod') != {'type':'Minute','value':5}:
            raise ValueError('Unreviewed bars period')
        if set(b['inputs']) != {'Fast','Slow'} or not 1 <= b['inputs']['Fast'] < b['inputs']['Slow'] <= 100:
            raise ValueError('Invalid SMA pair')
    if spec['engine'] == 'python' and spec['strategy'] not in {'breakout','retest','failed_ib'}:
        raise ValueError('Unreviewed Python strategy')

def fingerprint(spec):
    # Labels, priority and retry budget do not make a duplicate experiment new.
    keys = ('engine','strategy','symbol','dataset','data_hash','code_commit','code_hash','params','cost','request')
    return hashlib.sha256(canonical({k:spec.get(k) for k in keys}).encode()).hexdigest()

class Queue:
    def __init__(self, folder=DEFAULT_STATE, telemetry=DEFAULT_TELEMETRY):
        self.folder = Path(folder); self.folder.mkdir(parents=True, exist_ok=True)
        self.telemetry = Path(telemetry)
        self.db = self.folder/'queue.sqlite3'
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS jobs(
              id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, spec TEXT NOT NULL,
              status TEXT NOT NULL, phase TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
              attempts INTEGER NOT NULL DEFAULT 0, available REAL NOT NULL DEFAULT 0,
              created REAL NOT NULL, updated REAL NOT NULL, started REAL, deadline REAL,
              nt_id TEXT, nt_instance TEXT, reason TEXT NOT NULL DEFAULT '', result TEXT);
            CREATE TABLE IF NOT EXISTS control(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, time REAL, job TEXT, status TEXT, reason TEXT);
            INSERT OR IGNORE INTO control VALUES('mode','paused');
            INSERT OR IGNORE INTO control VALUES('uncertain','');
            ''')

    @contextlib.contextmanager
    def connect(self):
        c=sqlite3.connect(self.db, timeout=10); c.row_factory=sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA synchronous=FULL')
        try:
            yield c; c.commit()
        except BaseException:
            c.rollback(); raise
        finally:
            c.close()

    def control(self, key, value=None):
        with self.connect() as c:
            if value is not None:
                c.execute('INSERT OR REPLACE INTO control VALUES(?,?)',(key,value))
            row=c.execute('SELECT value FROM control WHERE key=?',(key,)).fetchone()
            return row[0] if row else ''

    def enqueue(self, spec):
        validate(spec); fp=fingerprint(spec); jid='nq-'+fp[:24]; now=time.time()
        with self.connect() as c:
            c.execute('INSERT OR IGNORE INTO jobs(id,fingerprint,spec,status,phase,created,updated) VALUES(?,?,?,?,?,?,?)',
                      (jid,fp,canonical(spec),'queued','대기',now,now))
        self.emit(jid)
        return jid

    def get(self,jid):
        with self.connect() as c:
            row=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            if not row: raise KeyError(jid)
            return dict(row)

    def rows(self):
        with self.connect() as c:
            return [dict(r) for r in c.execute('SELECT * FROM jobs ORDER BY created,id')]

    def update(self,jid,**kw):
        allowed={'status','phase','progress','attempts','available','started','deadline','nt_id','nt_instance','reason','result'}
        if not set(kw)<=allowed: raise ValueError('Invalid queue field')
        kw['updated']=time.time()
        with self.connect() as c:
            c.execute('UPDATE jobs SET '+','.join(k+'=?' for k in kw)+' WHERE id=?',(*kw.values(),jid))
            c.execute('INSERT INTO events(time,job,status,reason) VALUES(?,?,?,?)',
                      (time.time(),jid,kw.get('status',''),kw.get('reason',kw.get('phase',''))))
        self.emit(jid)

    def claim(self):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            mode=c.execute("SELECT value FROM control WHERE key='mode'").fetchone()[0]
            uncertain=c.execute("SELECT value FROM control WHERE key='uncertain'").fetchone()[0]
            if mode!='running' or uncertain or c.execute("SELECT 1 FROM jobs WHERE status='running'").fetchone():
                return None
            row=c.execute("SELECT * FROM jobs WHERE status='queued' AND available<=? ORDER BY created,id LIMIT 1",(time.time(),)).fetchone()
            if not row: return None
            c.execute("UPDATE jobs SET status='running',phase='preflight',progress=5,started=?,updated=? WHERE id=?",(time.time(),time.time(),row['id']))
            return row['id']

    def block(self,jid,reason,retry=False):
        row=self.get(jid); spec=json.loads(row['spec']); n=row['attempts']+1
        # Only pre-submission failures may retry, and at most twice.
        auto=retry and n<=spec.get('max_preflight_retries',1)
        self.update(jid,status='queued' if auto else 'blocked',phase='백오프' if auto else '선행 조건 대기',
                    attempts=n,available=time.time()+300*n,reason=reason,progress=0)

    def uncertain(self,jid,reason):
        self.control('uncertain',jid+': '+reason)
        self.control('mode','paused')
        self.update(jid,status='blocked',phase='수동 확인 필요 · 중복 제출 금지',reason=reason)

    def emit(self,jid):
        from dashboard.reporter import emit
        row=self.get(jid); spec=json.loads(row['spec']); result=json.loads(row['result']) if row['result'] else {}
        snapshot=dict(id=jid,batch=spec.get('batch','nq-finite-v1'),symbol='NQ',worker='windows-experiment-runner',
                      strategy=spec['strategy'],source=spec.get('source',spec['engine']),dataset=spec['dataset'],
                      data_hash=spec['data_hash'],code_commit=spec['code_commit'],cost=spec['cost']['label'],
                      params={**spec['params'],'engine':spec['engine'],'code_hash':spec['code_hash'],
                              'timeout_s':spec['timeout_s'],'attempts':row['attempts'],
                              'native_job_id':row['nt_id']},
                      status=row['status'],phase=row['phase'],progress=row['progress'],reason=row['reason'],
                      metrics=result.get('metrics',{}),equity=result.get('equity',[]),
                      evidence=spec.get('evidence','')+' '+result.get('evidence',''))
        if spec['engine']=='nt':
            # Request is authoritative even when a diagnostic was copied from another manifest case.
            snapshot['params'].update(from_date=spec['request']['from'],to_date=spec['request']['to'])
        if row['started']: snapshot['started_at']=row['started']
        if row['status'] in TERMINAL: snapshot['completed_at']=row['updated']
        try:
            emit(snapshot,self.telemetry)
        except (OSError, ValueError) as exc:
            # Persistence already succeeded; daemon will replay snapshots on its next cycle.
            self.control('telemetry_error',type(exc).__name__)

    def health(self, phase, current=None):
        value=dict(pid=os.getpid(),updated_at=time.time(),phase=phase,current_run=current,
                   mode=self.control('mode'),uncertain=self.control('uncertain'))
        atomic(self.folder/'health.json',value)

class ProcessLock:
    def __init__(self,path): self.path=Path(path); self.file=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('a+b')
        try:
            self.file.seek(0,os.SEEK_END)
            if self.file.tell()==0: self.file.write(b'0'); self.file.flush()
            self.file.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close(); self.file=None; raise RuntimeError('Runner already active')
        return self
    def __exit__(self,*args):
        if self.file: self.file.close()
