"""Read only existing verified historical results and emit extended scorecards."""
import json,re,unittest
from collections import defaultdict
from datetime import datetime
from runner.core import ROOT,atomic,file_hash
from research.trade_metrics import evaluate

def main():
    target=ROOT/'research/extended-metrics-review.json'
    hashes={};groups=defaultdict(list)
    def read(path):
        hashes[path]=file_hash(ROOT/path);return json.loads((ROOT/path).read_text())
    specs=[('bollinger','bollinger-return',48),('rsi2','rsi-repair-v2',48),('rsi2','rsi-extension-oct7-9',48),
        ('macd','macd-cross',48),('stochastic','stochastic',48),('nr7','nr7-history-extension',48),('nr7','nr7-rth',48),
        ('ofi','ofi-early',48),('ofi','ofi-late',48),('ofi','ofi-oct2',48),('ofi','ofi-oct5',48),('ofi','ofi-oct6',48),
        ('gap','gap-fade',None),('moving-momentum','moving-momentum',None),('channel','channel-cycle',None)]
    for name,folder,risk in specs:
        state=read('data/runner/'+folder+'/state.json')
        for row in state['experiments'].values():
            if folder=='channel-cycle' and row['phase']!='recent':continue
            if row.get('quality_correction') is None and folder=='channel-cycle' and row['assessment'].get('decision')=='execution_error':continue
            assert row['ack'] and row['doc']['state']=='done'
            request=row['request'];slip=request['slippageTicks'];doc=row['doc'];inputs=request['inputs']
            dates=[]
            for line in doc['output']:
                m=re.match(r'AUDIT (\d{8}) bars=(\d+) gap=(False|false)',line)
                if m and inputs['FirstDate']<=int(m[1])<=inputs['LastDate']:
                    assert int(m[2]) in (78,390)
                    dates.append(datetime.strptime(m[1],'%Y%m%d').date().isoformat())
            assert dates,(folder,'No verified session audit')
            assert all(d<'2026-10-25' for d in dates)
            fee=5 if slip==2 else 10;trades=doc['trades']
            net=sum(t['pnl']-fee*t['qty'] for t in trades)
            assert abs(net-row['assessment']['net_after_assumed_fee'])<1e-6
            groups[(name,fee)].append(dict(trades=trades,dates=sorted(set(dates)),run_ids=[row['run_id']],risk=risk,source=folder))
            # No second native NR7 baseline was run because zero entries; zero ledger can be repriced.
            if folder=='nr7-rth':
                assert slip==2 and len(trades)==0
                groups[(name,10)].append(dict(trades=[],dates=sorted(set(dates)),run_ids=[row['run_id']],risk=risk,source='nr7-rth zero-trade same source repriced; not independent run'))
    cafe=read('research/cafe-sparse-review.json')
    cycle=read('research/cafe-cycle-results-20261025.json')
    assert all(r['trades']==0 for r in cycle['rows'] if r['phase']=='recent')
    for suffix in ('','-20261012','-20261013','-20261014','-20261015'):
        extension=read('research/cafe-extension-results'+suffix+'.json')
        assert all(r['assessment']['trade_count']==0 for r in extension)
    for row in cafe['rows']:
        if row['settings']['fillResolution']!='High':continue
        inp=row['inputs'];variant=inp['Variant'];minutes=60 if variant==3 else inp['RangeMinutes']
        coverage=next(c for c in cafe['coverage'] if c['variant']==variant and c['effective_range_minutes']==minutes)
        dates=[datetime.strptime(x,'%Y%m%d').date().isoformat() for x in coverage['evaluated_dates']]
        fee=5 if row['settings']['slippageTicks']==2 else 10
        groups[('cafe-ib60' if variant==3 else 'cafe-retest'+str(minutes),fee)].append(dict(trades=row['trades'],dates=dates,run_ids=[row['run_id']],risk=None,source='HighTick1 positive ledger plus verified zero-trade extensions; Standard duplicates excluded'))
    frozen=read('research/equity-audit-immutable-inputs.json')
    assert all(file_hash(ROOT/p)==h for p,h in frozen.items())
    pathaudit=read('research/bollinger-equity-path-audit.json')
    cases=[]
    for (name,fee),parts in sorted(groups.items()):
        dates=[];trades=[]
        for part in parts:
            assert not set(dates)&set(part['dates']),(name,'Overlapping sessions')
            dates+=part['dates'];trades+=part['trades']
        m=evaluate(trades,dates,fee,parts[0]['risk'])
        if name=='bollinger':
            audit=next(r for r in pathaudit['aggregates'] if r['fee']==fee)
            assert audit['net']==m['net'] and audit['closed_trade_drawdown']==m['closed_trade_drawdown']['maximum']
            m['holding_path_dd_bounds']=[audit['holding_path_drawdown_lower'],audit['holding_path_drawdown_upper']]
        else:m['holding_path_dd_bounds']=None
        if m['trades']<10:verdict='sample_too_sparse_for_adoption'
        elif m['net']<=0:verdict='negative_after_cost_in_tested_variant'
        elif m['additional_cost_sensitivity'][-1]['net']<=0 or m['net_without_best_positive_day']<=0:verdict='positive_but_cost_or_concentration_fragile'
        else:verdict='descriptive_positive_only_no_independent_validation'
        cases.append(dict(candidate=name,fee_per_roundtrip=fee,metrics=m,verdict=verdict,verdict_note='Descriptive triage, not a new optimized pass/fail rule or statistical minimum of10trades',run_ids=[rid for p in parts for rid in p['run_ids']],sources=[p['source'] for p in parts],dates=sorted(dates)))
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromName('tests.test_trade_metrics'))
    assert result.wasSuccessful()
    report=dict(cases=cases,candidate_configurations=len(groups)//2,cost_cases=len(cases),native_runs=0,new_downloads=0,
        original_source_hashes=hashes,immutable_hashes=frozen,tests=dict(passed=True,count=result.testsRun,
        files={p:file_hash(ROOT/p) for p in ['research/trade_metrics.py','research/reevaluate_metrics.py','tests/test_trade_metrics.py']}),
        methodology='docs/extended-metrics-methodology-2026-10-25.md',future_outcomes_read=False,
        scope='12 retained/current native configurations; superseded/error runs, earlier parameter-development alternatives, old proxy/Doji/ORB baselines and diagnostic duplicate trades excluded; no claim all206registry records are independent tests.',
        selection_limits='Historical exploratory/post-selection; this expanded metric panel was defined after seeing old results. No revised ranking by hindsight, no changed frozen future plan.',
        unavailable=dict(deflated_sharpe='Effective independent trial count and comparable full trial return panel missing;206registry identities are not independent tests',
            pbo='No complete comparable trial-by-date matrix; no invented probability',calmar='No credible annualized return on9–15sessions',
            causal_entry_quality='Native bar MAE/MFE is holding-window conditional, not counterfactual signal markout',
            portfolio_correlation='Different windows and overlapping samples; no portfolio allocation claim'))
    assert all(file_hash(ROOT/p)==h for p,h in hashes.items())
    atomic(target,report)
    print(json.dumps([dict(candidate=r['candidate'],fee=r['fee_per_roundtrip'],**{k:r['metrics'][k] for k in ['trades','sessions','net','win_rate','realized_payoff_ratio','profit_factor','expectancy_per_trade']}) for r in cases if r['fee_per_roundtrip']==10],indent=2))

if __name__=='__main__':main()
