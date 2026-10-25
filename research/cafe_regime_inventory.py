"""Descriptive session coverage; never a retroactive strategy filter."""
import json
from statistics import median
from runner.core import ROOT,atomic,Queue,file_hash
from research.finalize_gap_fade import publish
import hashlib

def main():
    eth={}
    for name in ('rsi-extension-oct7-9-coverage.json','rsi-eth-coverage-v2.json'):
        report=json.loads((ROOT/'research'/name).read_text())
        if report['complete']:
            assert all(file_hash(s['path'])==s['sha256'] for s in report['sources'])
            for w in report['warmup']:
                if w['observed_bars']==200 and not w['missing_intervals']:eth[w['date']]=name
    stoch=json.loads((ROOT/'research/stochastic-coverage.json').read_text());data={day:list(bars.values()) for day,bars in stoch['sessions'].items()}
    for r in json.loads((ROOT/'research/nr7-history-chunk1-decoded.json').read_text()):data[r['date']]=r['bars']
    for r in json.loads((ROOT/'research/nr7-existing-minute-audit.json').read_text())['sessions']:data[r['date']]=r['bars']
    stats={}
    # JSON keys are lexical; sort indexed dictionaries by actual minute first.
    for day,bars in data.items():
        if day in stoch['sessions']:bars=[b for _,b in sorted(stoch['sessions'][day].items(),key=lambda x:int(x[0]))]
        assert len(bars)==390
        high=max(b['high'] for b in bars);low=min(b['low'] for b in bars);width=high-low;change=bars[-1]['close']-bars[0]['open']
        stats[day]=dict(rth_range_points=width,open_close_points=change,absolute_open_close_divided_by_range=abs(change)/width if width else None,source='rawLast' if day in stoch['sessions'] or day<'2026-09-28' else 'native_minute_not_independent_rawtick',existing_200bar_eth_coverage_report=eth.get(day),eth_native_cafe_parity='not newly tested')
    review=json.loads((ROOT/'research/cafe-sparse-review.json').read_text());groups=[]
    for group in review['coverage']:
        iso=lambda d:d[:4]+'-'+d[4:6]+'-'+d[6:]
        observed=[iso(d) for d in group['evaluated_dates'] if iso(d) in stats];remaining=[iso(d) for d in group['available_but_not_evaluated_dates'] if iso(d) in stats]
        def summary(dates):
            ranges=[stats[d]['rth_range_points'] for d in dates];ratios=[stats[d]['absolute_open_close_divided_by_range'] for d in dates]
            return dict(sessions=len(dates),range_min=min(ranges),range_median=median(ranges),range_max=max(ranges),directionality_min=min(ratios),directionality_median=median(ratios),directionality_max=max(ratios)) if dates else None
        old=summary(observed);new=summary(remaining)
        outside=[d for d in remaining if stats[d]['rth_range_points']<old['range_min'] or stats[d]['rth_range_points']>old['range_max']]
        groups.append(dict(variant=group['variant'],effective_range_minutes=group['effective_range_minutes'],observed=old,available_untried=new,available_untried_dates=remaining,existing_eth_covered_untried=[d for d in remaining if d in eth],untried_range_outside_observed_span=outside,interpretation='Same September/October contract and nearby calendar window;range/directionality dispersion is descriptive,not independent broad-regime evidence. Existing200bar ETHreports reused where present;September warmup unverified. Technical data feasibility alone does not justify routine date expansion without a distinct research question.'))
    report=dict(sessions=stats,groups=groups,native_runs=0,metrics_role='Posthoc descriptive coverage only;full-session outcome metrics must never filter earlier entries',missing=['Priorregime/month/rollover coverage','Complete ETHindicator context for untried dates','Counterfactual PnL for risk-cap-rejected signals'],risk_cap_unchanged=300)
    atomic(ROOT/'research/cafe-regime-inventory.json',report)
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
    for row in review['rows']:
        row['assessment']['regime_inventory']='research/cafe-regime-inventory.json';row['assessment']['regime_interpretation']='Available untried dates remain nearby September/October history;Oct7-9 andOct19-22 reuse existing200bar ETHcoverage where applicable. September warmup remains unverified;no independent broadregime validation established';publish(row,q,config)
    review['regime_review_acks']=review.get('regime_review_acks',0)+len(review['rows']);review['regime_inventory']='research/cafe-regime-inventory.json';atomic(ROOT/'research/cafe-sparse-review.json',review)
    print(json.dumps(dict(groups=groups,metadata_acks=len(review['rows'])),indent=2))

if __name__=='__main__':main()
