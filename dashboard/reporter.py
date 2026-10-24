"""Windows outbound-only telemetry. Python stdlib; no account/market raw data sent."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

def post(url, path, data, token=''):
    req = Request(url.rstrip('/')+path, json.dumps(data,allow_nan=False).encode(), {'Content-Type':'application/json','Authorization':'Bearer '+token},method='POST')
    with urlopen(req,timeout=20) as r: return json.load(r)

def atomic(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8'); os.replace(tmp,path)

def emit(run, folder=None):
    folder=Path(folder) if folder else ROOT/'data/telemetry'
    # File path derives from hash, never from an untrusted run ID.
    atomic(folder/(hashlib.sha256(run['id'].encode()).hexdigest()+'.json'),run)

def main():
    p=argparse.ArgumentParser();p.add_argument('--url');p.add_argument('--pair-code');p.add_argument('--worker',default='windows-research');p.add_argument('--once',action='store_true');p.add_argument('--folder',type=Path,default=ROOT/'data/telemetry');p.add_argument('--config',type=Path,default=ROOT/'.dashboard-worker.json');args=p.parse_args()
    if args.pair_code:
        if not args.url or not args.url.startswith('https://'):p.error('HTTPS URL required for pairing')
        token=post(args.url,'/api/pair',{'code':args.pair_code})['token'];atomic(args.config,{'url':args.url,'token':token})
        try:args.config.chmod(0o600)
        except OSError:pass
        print('Worker paired. Credential saved locally; not printed.',flush=True)
    config=json.loads(args.config.read_text());url=config['url'];token=config['token']
    if not url.startswith('https://') and not url.startswith('http://127.0.0.1:'):p.error('HTTPS required')
    statepath=args.config.with_name('.dashboard-state.json')
    sent=json.loads(statepath.read_text()) if statepath.exists() else {}
    args.folder.mkdir(parents=True,exist_ok=True)
    while True:
        errors=0; uploaded=0; running=[]
        for file in sorted(args.folder.glob('*.json')):
            try:
                raw=file.read_bytes();run=json.loads(raw)
                if run.get('status')=='running':running.append(run['id'])
                sha=hashlib.sha256(raw).hexdigest()
                if sent.get(file.name)==sha:continue
                run['worker']=args.worker;post(url,'/api/runs',run,token)
                sent[file.name]=sha;atomic(statepath,sent);uploaded+=1
            except Exception as e:
                errors+=1;print(f'Upload pending: {file.name}: {type(e).__name__}',flush=True)
        try:
            post(url,'/api/heartbeat',{'id':args.worker,'label':'Windows · NinjaTrader 연구','phase':'reporting','current_run':running[0] if running else None,'message':f'결과 전달 중 · 미전송 {errors}건' if errors else '결과 동기화 정상 · 실험 상태는 아래 목록 참조'},token)
            if uploaded:print(f'Uploaded {uploaded} experiments',flush=True)
        except Exception as e:print(f'Heartbeat pending: {type(e).__name__}',flush=True)
        if args.once:break
        time.sleep(15)

if __name__=='__main__':main()
