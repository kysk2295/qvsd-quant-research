"""Read-only data + Backtest-account-only bridge adapter. No order endpoints."""
import json
import math
import sys
from urllib.request import Request, urlopen
from .core import ROOT, atomic, dataset_hash, file_hash

class Bridge:
    def call(self, method, path, body=None):
        allowed = ((method == 'GET' and path in ('/health','/backtests')) or
                   (method == 'POST' and path == '/backtest') or
                   (method in ('GET','DELETE') and path.startswith('/backtest/') and
                    path[len('/backtest/'):].isalnum()))
        if not allowed: raise ValueError('Endpoint outside research allowlist')
        req=Request('http://127.0.0.1:7891'+path,
                    json.dumps(body).encode() if body is not None else None,
                    {'Content-Type':'application/json'},method=method)
        with urlopen(req,timeout=5) as response: return json.load(response)

def verify_files(spec):
    files=spec['files']
    if not files or dataset_hash(files)!=spec['data_hash']:
        raise ValueError('Dataset missing or changed; new manifest required')
    if dataset_hash(spec['code_files'])!=spec['code_hash']:
        raise ValueError('Code changed; new manifest required')

def native_result(doc,spec):
    settings=doc.get('settings',{})
    # Effective fills must be present; reject silently ignored cost assumptions.
    if settings.get('slippageTicks') != spec['cost']['slippage_ticks']:
        raise ValueError('Native slippage readback mismatch')
    trades=doc.get('trades')
    if not isinstance(trades,list) or len(trades)!=doc.get('summary',{}).get('trades'):
        raise ValueError('Full native trade history required for cost reconstruction')
    fee=spec['cost']['round_trip_fee']; pnl=[]; curve=[]; eq=150000.; peak=eq; dd=0
    for trade in trades:
        net=float(trade['pnl'])-fee*int(trade['qty'])
        if not math.isfinite(net): raise ValueError('Non-finite native PnL')
        pnl.append(net);eq+=net;peak=max(peak,eq);dd=max(dd,peak-eq)
        curve.append({'date':str(trade['exitTime']),'value':round(eq,2)})
    losses=-sum(x for x in pnl if x<0); gains=sum(x for x in pnl if x>0)
    return dict(metrics=dict(net=round(sum(pnl),2),trades=len(pnl),closed_trade_mdd=round(dd,2),
                             profit_factor=gains/losses if losses else None,
                             win_pct=100*sum(x>0 for x in pnl)/len(pnl) if pnl else 0),equity=curve[-3000:],
                evidence='Native settings verified; assumed commission deducted per contract round trip. '
                         +'Loaded bars: '+str(doc.get('barsFrom'))+' .. '+str(doc.get('barsTo'))
                         +'; warnings: '+str(doc.get('warnings',[])),
                reason='실제 NT 비교용 계산 완료. 짧은 표본·기본 SMA·대회 위험 제약 미구현: 채택 불가.')

def python_run(spec):
    from research import backtest as bt
    verify_files(spec)
    bt.SPECS['NQ']['point']=20.0  # NQ, explicitly not the legacy MNQ $2 multiplier.
    sessions,audit=bt.load('NQ'); p=spec['params'];cost=spec['cost']
    selected={d:b for d,b in sessions.items() if p['from']<=d<=p['to']}
    if not selected: raise ValueError('No complete sessions in requested period')
    trades,daily,extra=bt.run(selected,'NQ',spec['strategy'],cost['slippage_ticks'],
                             cost['round_trip_fee'],p['or_minutes'],max_contracts=8)
    m=bt.metrics(trades,daily);m.update(extra)
    m['net_without_best3']=round(m['net']-sum(sorted((t['pnl'] for t in trades),reverse=True)[:3]),2)
    return dict(metrics=m,equity=[dict(date=d['date'],value=d['equity']) for d in daily],
                evidence='Yahoo NQ price proxy; $20/point; max8; next-bar fills; complete RTH sessions. '
                         'Previously examined data: chronological diagnostic, NOT independent OOS.',
                reason='비용 후 손익 0 이하: 이 설정 탈락' if m['net']<=0 else
                       '예비 계산 완료. 표본·체결·대회 계좌 위험 검증 전: 채택 미승인.',
                rejected=m['net']<=0)

if __name__=='__main__':
    from pathlib import Path
    spec=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    atomic(Path(sys.argv[2]),python_run(spec))
