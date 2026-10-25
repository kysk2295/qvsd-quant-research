"""Finite, predefined comparison grid. No adaptive search over validation results."""
import copy
import subprocess
from pathlib import Path
from .core import ROOT, dataset_hash

def build():
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    code=[ROOT/'research/backtest.py',*sorted((ROOT/'runner').glob('*.py'))]
    base=dict(symbol='NQ',code_commit=commit,code_files=[str(p) for p in code],code_hash=dataset_hash(code),
              timeout_s=180,max_preflight_retries=1,batch='nq-finite-v1',evidence='runner/README.md',
              params={},cost=dict(label='base-assumed',slippage_ticks=2,round_trip_fee=5.0))
    specs=[]
    native_files=sorted((Path.home()/'Documents/NinjaTrader 8/db/minute/NQ 12-26').glob('*.ncd'))
    strategy_file=Path.home()/'Documents/NinjaTrader 8/bin/Custom/Strategies/@SampleMACrossOver.cs'
    for start,end,role in [('2026-09-28','2026-09-29','earlier-smoke'),('2026-09-30','2026-10-01','later-smoke')]:
        for fast,slow in [(10,25),(15,40)]:
            for label,slip,fee in [('base-assumed',2,5.0),('stress-assumed',4,10.0)]:
                s=copy.deepcopy(base);s.update(engine='nt',strategy='SampleMACrossOver',source='NT 실제 백테스트 · 기능 비교용',
                    files=[str(p) for p in native_files],data_hash=dataset_hash(native_files),dataset=start+' .. '+end+' NQ 12-26 5m',
                    params=dict(Fast=fast,Slow=slow,role=role,from_date=start,to_date=end),
                    cost=dict(label=label,slippage_ticks=slip,round_trip_fee=fee))
                s['code_files'].append(str(strategy_file));s['code_hash']=dataset_hash(s['code_files'])
                s['request']=dict(strategy='SampleMACrossOver',instrument='NQ 12-26',barsPeriod=dict(type='Minute',value=5),
                    inputs=dict(Fast=fast,Slow=slow),tickReplay=False,fillResolution='Standard',slippageTicks=slip,
                    includeCommission=False,fillLimitOnTouch=False,includeTradeHistory=True,breakAtEod=True,
                    **{'from':start,'to':end})
                specs.append(s)
    file=ROOT/'research/data/NQ_5m.json'
    for start,end,role in [('2026-08-14','2026-10-02','earlier-diagnostic'),('2026-10-05','2026-10-23','later-diagnostic')]:
        for strategy,minutes in [('breakout',15),('breakout',30),('retest',15),('retest',30),('failed_ib',60)]:
            for label,slip,fee in [('base-assumed',2,5.0),('stress-assumed',4,10.0)]:
                s=copy.deepcopy(base);s.update(engine='python',strategy=strategy,source='Python 가격 대리 탐색 · NQ $20/point',
                    files=[str(file)],data_hash=dataset_hash([file]),dataset=start+' .. '+end+' Yahoo NQ 5m',
                    params=dict(or_minutes=minutes,role=role,point_value=20,max_contracts=8,**{'from':start,'to':end}),
                    cost=dict(label=label,slippage_ticks=slip,round_trip_fee=fee))
                specs.append(s)
    s=copy.deepcopy(base);s.update(engine='blocked',strategy='orderflow_confirmation',source='L2 데이터 선행 조건',
        dataset='NQ L1/L2 multiple sessions required',data_hash='unavailable',
        blocked_reason='다일 NQ L1/L2와 세션별 결손 검증 부족. OFI·델타 전략 검증 불가; 자동 재시도 없음.')
    specs.append(s)
    assert len(specs)==29
    return specs
