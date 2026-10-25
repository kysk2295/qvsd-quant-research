"""Three audited warmup files, one guarded native import submission each."""
import json,time,urllib.request
from runner.core import ROOT,atomic,file_hash
from research.prepare_nt_ticks import prepare

def call(method,body=None):
    req=urllib.request.Request('http://localhost:7891/research/import',data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'},method=method)
    with urllib.request.urlopen(req,timeout=45) as response:return json.load(response)

def main():
    reports=json.loads((ROOT/'research/nr7-history-chunk1-decoded.json').read_text());assert len(reports)==3
    path=ROOT/'research/nr7-warmup-imports.json';state=json.loads(path.read_text()) if path.exists() else {}
    for report in reports:
        day=report['date'];compact=day.replace('-','')
        if day in state:
            assert state[day].get('state')=='done','Uncertain previous import;do not resubmit'
            continue
        source=ROOT/f'data/incoming/replay/2026/NQ-2026_L1/{compact}.parquet'
        assert file_hash(source)==report['parquet_sha256'] and report['integrity_passed']
        dest=ROOT/f'data/runner/nt-import/{compact}/NQ DEC26.Last.txt'
        prepared=prepare(source,dest)
        state[day]=dict(state='submitting',prepared=prepared);atomic(path,state)
        response=call('POST',dict(path=str(dest),sha256=prepared['output_sha256']));state[day]['submission']=response;atomic(path,state)
        deadline=time.time()+180
        while True:
            result=call('GET');state[day]['latest']=result;atomic(path,state)
            assert result.get('path')==str(dest)
            if result['state'] not in ('running','queued'):break
            if time.time()>deadline:raise RuntimeError('Import deadline;inspect existing job,never resubmit')
            time.sleep(1)
        assert result['state']=='done' and result['points']==prepared['rows']
        state[day]['state']='done';atomic(path,state)
        print(json.dumps(dict(date=day,state='done',points=result['points'])),flush=True)

if __name__=='__main__':main()
