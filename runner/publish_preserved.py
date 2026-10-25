"""Publish preserved native diagnostics, never execute or enqueue a strategy."""
import json, hashlib, subprocess, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.request import urlopen
from runner.core import ROOT, Queue, file_hash, dataset_hash, atomic
from dashboard.reporter import emit, post
from dashboard.server import validate_run

def publish():
    q=Queue()
    config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
    files=sorted((Path.home()/'Documents/NinjaTrader 8/db/minute/NQ 12-26').glob('*.ncd'))
    observed_hash=dataset_hash(files)
    batches=[('native-scalpers-20261006.json','ee68498','native-scalpers-backtest-2026-10-25.md'),
             ('public-orb-batch1.json','495f4a6','orb-research-batch.md'),
             ('close-momentum-batch2.json','95d2123','close-momentum-batch.md')]
    sent=[]
    for filename,commit,report in batches:
        ledger=ROOT/'data/runner'/filename
        for d in json.loads(ledger.read_text()):
            assert d['state']=='done' and d['timeZone']=='Korea Standard Time'
            assert len(d['trades'])==d['summary']['trades']
            s=d['settings'];slip=s['slippageTicks']
            assert slip in (2,4) and not s['includeCommission'] and s['includeTradeHistory']
            fee=5 if slip==2 else 10
            identity={k:d[k] for k in ['strategy','inputs','startedAt','finishedAt','settings','trades']}
            digest=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
            jid='native-audit-'+digest[:24]
            path=ROOT/'native'/f"{d['strategy']}.cs"
            if path.exists():
                source_hash=file_hash(path)
            else:
                source_hash=json.loads((ROOT/'data/runner/native-scalpers-source-hash.json').read_text(encoding='utf-8-sig'))['Hash'].lower()
            pnl=[t['pnl']-fee*t['qty'] for t in d['trades']]
            total=0;peak=0;dd=0;curve=[]
            for trade,net in zip(d['trades'],pnl):
                total+=net;peak=max(peak,total);dd=max(dd,peak-total)
                curve.append(dict(date=trade['exitTime'],value=150000+total))
            run=dict(id=jid,batch='preserved-native-diagnostics',symbol='NQ',worker='windows-experiment-runner',
                strategy=d['strategy'],source='NinjaTrader internal engine; preserved ledger import',
                dataset=d['barsFrom']+' .. '+d['barsTo']+' KST, NQ DEC26 1m',
                data_hash='run-time dataset hash unavailable',
                code_commit=subprocess.check_output(['git','rev-parse',commit],cwd=ROOT,text=True).strip(),
                status='rejected' if total<=0 else 'completed',phase='기존 원장 동기화 · 재실행 없음',progress=100,
                reason='예비 진단: 비용 후 손실' if total<=0 else '예비 계산 양수; 채택 불가, Replay/OOS 미검증',
                cost=f'{slip} ticks native + assumed USD {fee} round trip',
                params=dict(inputs=d['inputs'],native_id=d['id'],native_started=d['startedAt'],
                    actual_bars_from=d['barsFrom'],actual_bars_to=d['barsTo'],settings=s,
                    source_hash_observed=source_hash,dataset_hash_observed_after_run=observed_hash,
                    hash_provenance='Source/current files observed retrospectively; run-time data hash not captured',
                    requested_from=d['from'],requested_to=d['to'],tick_replay=d['tickReplay'],
                    market_replay=False,independent_oos=False,ledger_hash=file_hash(ledger)),
                metrics=dict(net=total,trades=len(pnl),closed_trade_mdd=dd,
                    native_net_before_assumed_fee=d['summary']['netProfit']),
                equity=curve,
                started_at=datetime.fromisoformat(d['startedAt']).replace(tzinfo=ZoneInfo('Asia/Seoul')).timestamp(),
                completed_at=datetime.fromisoformat(d['finishedAt']).replace(tzinfo=ZoneInfo('Asia/Seoul')).timestamp(),
                evidence=f'docs/{report}; NQ adaptations, minute-bar diagnostic. Not original ETF return reproduction. '
                    'No independent OOS, no Market Replay, no Strategy Analyzer UI reproduction. '
                    'Effective evaluation dates audited separately; not proof requested whole range is complete. '
                    'Previous invalid records retained. Runtime data fingerprint unavailable.')
            validate_run(run);emit(run,q.telemetry)
            snap=q.telemetry/(hashlib.sha256(jid.encode()).hexdigest()+'.json')
            if q.control('ack:'+snap.name)!=file_hash(snap):
                response=post(config['url'],'/api/runs',run,config['token'])
                if response.get('ok') is not True:raise RuntimeError('No server ACK')
            q.control('ack:'+snap.name,file_hash(snap));sent.append(jid)
    atomic(ROOT/'data/runner/native-sync-ack.json',dict(ids=sent,acknowledged=len(sent),time=time.time()))
    print(json.dumps(dict(acknowledged=len(sent),ids=sent,readback='Requires browser session; worker token is write-only'),indent=2))
if __name__=='__main__':publish()
