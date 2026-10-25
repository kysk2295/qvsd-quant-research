"""Publish preserved cafe cycle diagnostics; never enqueue or execute strategies."""
import json,hashlib,subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
from runner.core import ROOT,Queue,file_hash,atomic
from dashboard.reporter import emit,post
from dashboard.server import validate_run

def main():
    q=Queue()
    config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text(encoding='utf-8'))
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    source_hash=file_hash(ROOT/'native/CodexCafeRange.cs')
    sent=[]
    for phase in ('development','recent','high-resolution'):
        path=ROOT/'data/runner'/('cafe-'+phase+'-20261025.json')
        for d in json.loads(path.read_text(encoding='utf-8')):
            assert d['state']=='done' and not d['error'] and d['strategy']=='CodexCafeRange'
            fee=5 if d['settings']['slippageTicks']==2 else 10
            identity=json.dumps(d,sort_keys=True).encode()
            jid='cafe-native-'+hashlib.sha256(identity).hexdigest()[:24]
            net=sum(t['pnl']-fee*t['qty'] for t in d['trades'])
            run=dict(id=jid,strategy='CodexCafeRange',symbol='NQ',worker='windows-experiment-runner',
                     batch='cafe-cycle-20261025',source='NinjaTrader native historical engine',
                     dataset=d['barsFrom']+' .. '+d['barsTo']+' KST, NQ DEC26 5m',
                     data_hash='runtime snapshot not captured; raw-file hashes in recent tick audit',
                     code_commit=commit,status='rejected',progress=100,phase=phase,
                     reason='최근 위험 한도 초과로 진입 0건' if phase=='recent' else '거래 수 부족·수익 집중으로 채택 불가',
                     cost=str(d['settings']['slippageTicks'])+' ticks + assumed $'+str(fee)+' round trip',
                     metrics=dict(net=net,trades=len(d['trades']),native_net_before_assumed_fee=d['summary']['netProfit']),
                     params=dict(inputs=d['inputs'],settings=d['settings'],source_hash=source_hash,
                                 ledger_hash=file_hash(path),independent_oos=False,strategy_replay=False),
                     equity=[],
                     started_at=datetime.fromisoformat(d['startedAt']).replace(tzinfo=ZoneInfo('Asia/Seoul')).timestamp(),
                     completed_at=datetime.fromisoformat(d['finishedAt']).replace(tzinfo=ZoneInfo('Asia/Seoul')).timestamp(),
                     evidence='docs/nq-validation-cycle-2026-10-25.md; recent four-day raw tick audit; separate transport-only Replay passed, no strategy fill validation. $300 is a research assumption.')
            validate_run(run);emit(run,q.telemetry)
            snap=q.telemetry/(hashlib.sha256(jid.encode()).hexdigest()+'.json')
            if q.control('ack:'+snap.name)!=file_hash(snap):
                response=post(config['url'],'/api/runs',run,config['token'])
                if response.get('ok') is not True:raise RuntimeError('No server ACK')
            q.control('ack:'+snap.name,file_hash(snap));sent.append(jid)
    atomic(ROOT/'data/runner/cafe-sync-ack.json',dict(acknowledged=len(sent),ids=sent))
    print(json.dumps(dict(acknowledged=len(sent))))

if __name__=='__main__':main()
