"""Finite 12-case reproduction, with real progress. Not native NT data validation."""
import argparse
import hashlib
import subprocess
import sys
import time
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import backtest
from reporter import emit

def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path);a=p.parse_args()
    batch='proxy-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=backtest.ROOT,text=True).strip()
    for symbol in ('NQ','GC'):
        sessions,audit=backtest.load(symbol)
        for strategy in ('breakout','retest','failed_ib'):
            for cost,slip,fee in [('base',2,2.5),('stress',4,5.0)]:
                r=dict(id=f'{batch}-{symbol}-{strategy}-{cost}',batch=batch,strategy=strategy,symbol=symbol,cost=cost,status='queued',progress=0,phase='실험 대기',worker='windows-research',source='Yahoo 대리 데이터 · 재현 실험',dataset=f"{min(sessions)} ~ {max(sessions)} · 5분봉",params=dict(slippage_ticks=slip,round_trip_fee=fee,risk_per_entry=300,max_micro_contracts=10),code_commit=commit,data_hash=audit['sha256'],started_at=time.time(),reason='마이크로 계약가치 대리 검증. 대회 시간·합산 위험·실제 체결은 미검증.',evidence='research/backtest.py · 기존 규칙 재현 / 독립 검증 아님')
                emit(r,a.folder)
                try:
                    r.update(status='running',phase='과거 데이터 계산',progress=20);emit(r,a.folder)
                    trades,daily,extra=backtest.run(sessions,symbol,strategy,slip,fee)
                    r.update(status='completed',phase='재현 계산 완료 · 채택 미평가',progress=100,metrics={**backtest.metrics(trades,daily),**extra},equity=[{'date':d['date'],'value':d['equity']} for d in daily],completed_at=time.time());emit(r,a.folder)
                    print(r['id'],r['metrics']['net'],flush=True)
                except Exception as e:
                    r.update(status='failed',phase='실험 오류',reason=str(e)[:400],completed_at=time.time());emit(r,a.folder)
                    raise
if __name__=='__main__':main()
