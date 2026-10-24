"""Single-user research telemetry. No trade execution or remote command endpoint."""
import hashlib
import hmac
import json
import math
import os
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs
from contextlib import contextmanager

BASE = Path(__file__).resolve().parent
DB = Path(os.environ.get('DASHBOARD_DB', BASE / 'local.sqlite3'))
PASSWORD = os.environ.get('DASHBOARD_PASSWORD', '')
INGEST = os.environ.get('INGEST_TOKEN', '')
PAIR = os.environ.get('PAIRING_CODE', '')
SECURE = os.environ.get('COOKIE_SECURE', '1') == '1'
STATUSES = {'queued', 'running', 'completed', 'failed', 'rejected', 'blocked'}

@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    try:
        with c:
            yield c
    finally:
        c.close()

def init():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS workers(id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, run_id TEXT, message TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS credentials(hash TEXT PRIMARY KEY, kind TEXT NOT NULL, created REAL);
        CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY, count INTEGER, started REAL);
        ''')
        # Archived public proxy results, never presented as current Windows runs.
        if not c.execute('SELECT 1 FROM runs LIMIT 1').fetchone():
            seed = BASE / 'baseline.json'
            if seed.exists():
                for r in json.loads(seed.read_text(encoding='utf-8')):
                    c.execute('INSERT INTO runs VALUES(?,?,?)', (r['id'], json.dumps(r), r['updated_at']))

def digest(v): return hashlib.sha256(v.encode()).hexdigest()
def equal(a, b): return bool(a and b) and hmac.compare_digest(a.encode(), b.encode())
def session_value():
    expiry = str(int(time.time()) + 7 * 86400)
    return expiry + '.' + hmac.new(PASSWORD.encode(), expiry.encode(), hashlib.sha256).hexdigest()
def session_ok(env):
    try:
        cookie = SimpleCookie(env.get('HTTP_COOKIE', ''))
        token = cookie['qvsd_session'].value
        expiry, sig = token.split('.')
        return int(expiry) > time.time() and equal(sig, hmac.new(PASSWORD.encode(), expiry.encode(), hashlib.sha256).hexdigest())
    except (KeyError, ValueError): return False

def writer_ok(env):
    token = env.get('HTTP_AUTHORIZATION', '').removeprefix('Bearer ')
    if equal(token, INGEST): return True
    with connect() as c:
        return bool(token and c.execute('SELECT 1 FROM credentials WHERE hash=? AND kind=?', (digest(token), 'worker')).fetchone())

def limit(key):
    now = time.time()
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT * FROM limits WHERE key=?', (key,)).fetchone()
        count = row['count'] + 1 if row and now - row['started'] < 300 else 1
        start = row['started'] if row and now - row['started'] < 300 else now
        c.execute('INSERT OR REPLACE INTO limits VALUES(?,?,?)', (key, count, start))
        c.execute('DELETE FROM limits WHERE started < ?', (now - 600,))
    return count <= 20

def validate_run(r):
    if not isinstance(r, dict): raise ValueError('run must be an object')
    for k in ('id', 'strategy', 'symbol', 'source', 'worker', 'dataset', 'status'):
        if not isinstance(r.get(k), str) or not r[k] or len(r[k]) > 180:
            raise ValueError('invalid ' + k)
    if r['status'] not in STATUSES: raise ValueError('invalid status')
    p = r.get('progress', 0)
    if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 100:
        raise ValueError('invalid progress')
    for v in r.get('metrics', {}).values():
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)):
            raise ValueError('metrics must be finite numbers or null')
    curve = r.get('equity', [])
    if not isinstance(curve, list) or len(curve) > 3000: raise ValueError('invalid equity curve')
    for point in curve:
        if not isinstance(point, dict) or not isinstance(point.get('date'), str) or not isinstance(point.get('value'), (int, float)) or not math.isfinite(point['value']):
            raise ValueError('invalid equity point')
    # Explicit allowed metadata only; no arbitrary account or raw tick fields persisted.
    keys = ('id','strategy','symbol','source','worker','dataset','status','progress','phase','reason','cost','metrics','params','equity','started_at','completed_at','evidence','data_hash','code_commit','batch')
    return {k: r[k] for k in keys if k in r}

def application(env, start_response):
    path, method = env.get('PATH_INFO', '/'), env['REQUEST_METHOD']
    headers = [('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','same-origin'),('X-Frame-Options','DENY'),('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'self'; frame-ancestors 'none'")]
    def response(code, value, mime='application/json', extra=()):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode() if mime == 'application/json' else value.encode() if isinstance(value, str) else value
        start_response(code, headers + [('Content-Type', mime), ('Content-Length', str(len(data)))] + list(extra))
        return [data]
    try:
        if path == '/healthz': return response('200 OK', {'ok': True})
        if path in ('/app.css','/app.js') and method == 'GET':
            return response('200 OK', (BASE/'static'/path[1:]).read_bytes(), 'text/css' if path.endswith('css') else 'application/javascript')
        if not PASSWORD: return response('503 Service Unavailable', {'error':'Dashboard password is not configured'})
        if method == 'POST':
            size = int(env.get('CONTENT_LENGTH') or '0')
            if size <= 0 or size > 1_000_000: return response('413 Payload Too Large', {'error':'Request size outside bounds'})
            raw = env['wsgi.input'].read(size)
            # Same-origin browser writes. Native reporters don't send an Origin header.
            origin = env.get('HTTP_ORIGIN')
            expected_origin = os.environ.get('PUBLIC_ORIGIN') or ('https' if SECURE else 'http') + '://' + env.get('HTTP_HOST','')
            if origin and origin != expected_origin:
                print('Rejected origin', repr(origin), 'expected', repr(expected_origin), flush=True)
                return response('403 Forbidden', {'error':'Origin rejected'})
            if path == '/login':
                if not limit('login:' + env.get('REMOTE_ADDR', '')): return response('429 Too Many Requests', {'error':'잠시 후 다시 시도해주세요.'})
                pw = parse_qs(raw.decode()).get('password',[''])[0]
                if not equal(pw, PASSWORD):
                    return response('401 Unauthorized', login_page(True), 'text/html; charset=utf-8')
                cookie = 'qvsd_session=' + session_value() + '; Path=/; HttpOnly; SameSite=Strict; Max-Age=604800' + ('; Secure' if SECURE else '')
                return response('303 See Other', '', 'text/plain', [('Location','/'), ('Set-Cookie',cookie)])
            if path == '/logout':
                return response('303 See Other','', 'text/plain', [('Location','/'),('Set-Cookie','qvsd_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict')])
            body = json.loads(raw)
            if path == '/api/pair':
                if not limit('pair:' + env.get('REMOTE_ADDR','')): return response('429 Too Many Requests', {'error':'Try later'})
                if not equal(str(body.get('code','')), PAIR): return response('401 Unauthorized', {'error':'Invalid pairing code'})
                with connect() as c:
                    c.execute('BEGIN IMMEDIATE')
                    if c.execute('SELECT 1 FROM credentials WHERE hash=?', (digest(PAIR),)).fetchone():
                        return response('409 Conflict', {'error':'Pairing code already used'})
                    token = secrets.token_urlsafe(40)
                    c.execute('INSERT INTO credentials VALUES(?,?,?)', (digest(PAIR),'pair_used',time.time()))
                    c.execute('INSERT INTO credentials VALUES(?,?,?)', (digest(token),'worker',time.time()))
                return response('200 OK', {'token':token})
            if not writer_ok(env): return response('401 Unauthorized', {'error':'Worker authentication required'})
            if path == '/api/heartbeat':
                worker = body.get('id')
                if not isinstance(worker,str) or not 0 < len(worker) <= 120: raise ValueError('Invalid worker')
                payload = {k:body[k] for k in ('id','label','phase','current_run','message') if k in body}
                with connect() as c:
                    c.execute('INSERT OR REPLACE INTO workers VALUES(?,?,?)', (worker,json.dumps(payload),time.time()))
                return response('200 OK', {'ok':True})
            if path == '/api/runs':
                r = validate_run(body); now = time.time(); r['updated_at'] = now
                with connect() as c:
                    old = c.execute('SELECT payload FROM runs WHERE id=?',(r['id'],)).fetchone()
                    old = json.loads(old['payload']) if old else None
                    # Reject an older reporter snapshot if revisions are supplied by SDK.
                    if old and old.get('completed_at') and r['status'] in ('queued','running'):
                        return response('409 Conflict', {'error':'Use a new run ID to rerun a terminal experiment'})
                    c.execute('INSERT OR REPLACE INTO runs VALUES(?,?,?)',(r['id'],json.dumps(r,allow_nan=False),now))
                    if not old or old['status'] != r['status'] or old.get('phase') != r.get('phase'):
                        msg = f"{r['strategy']} · {r['symbol']} · {r['status']} · {str(r.get('phase',r.get('reason','')))[:350]}"
                        c.execute('INSERT INTO events(run_id,message,created) VALUES(?,?,?)',(r['id'],msg,now))
                        c.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 1000)')
                return response('200 OK', {'ok':True})
            return response('404 Not Found', {'error':'Not found'})
        if method != 'GET': return response('405 Method Not Allowed', {'error':'Method not allowed'})
        if not session_ok(env):
            if path.startswith('/api/'): return response('401 Unauthorized', {'error':'Login required'})
            return response('200 OK', login_page(), 'text/html; charset=utf-8')
        if path == '/': return response('200 OK',(BASE/'static'/'index.html').read_bytes(),'text/html; charset=utf-8')
        if path == '/api/state':
            now = time.time()
            with connect() as c:
                runs = [json.loads(x['payload']) for x in c.execute('SELECT * FROM runs ORDER BY updated DESC LIMIT 2000')]
                workers = [{**json.loads(x['payload']), 'updated_at':x['updated'], 'online':now-x['updated']<45} for x in c.execute('SELECT * FROM workers')]
                events = [dict(x) for x in c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 80')]
            return response('200 OK', {'runs':runs,'workers':workers,'events':events,'server_time':now})
        return response('404 Not Found', {'error':'Not found'})
    except (ValueError, TypeError, AttributeError, UnicodeError) as e:
        return response('400 Bad Request', {'error':str(e)[:180]})
    except Exception:
        import traceback; traceback.print_exc()
        return response('500 Internal Server Error', {'error':'Internal server error'})

def login_page(error=False):
    return '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>QUANT LAB · 로그인</title><link rel="stylesheet" href="/app.css"><body class="login"><form action="/login" method="post" class="login-card"><div class="brand">Q<span> / </span>LAB</div><div class="eyebrow">PRIVATE RESEARCH WORKSPACE</div><h1>실험의 모든 순간을,<br>한 곳에서.</h1><p>전략 연구 대시보드에 접속하세요.</p><label>접속 비밀번호<input type="password" name="password" autocomplete="current-password" required autofocus></label>''' + ('<p class="negative">비밀번호를 확인해주세요.</p>' if error else '') + '''<button class="primary">대시보드 열기 →</button><small>실험 결과와 작업 현황을 위한 공간 · 주문 기능 없음</small></form></body></html>'''

init()
if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    make_server('127.0.0.1',int(os.getenv('PORT','8080')),application).serve_forever()
