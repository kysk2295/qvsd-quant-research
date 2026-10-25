"""Freeze a distinct historical window after contiguous daily-context audit."""
import json,time
from datetime import date,timedelta
from runner.core import ROOT,atomic,file_hash
from runner.research_protocol import validate_manifest

def main():
    target=ROOT/'research/nr7-history-extension-manifest.json'
    assert not target.exists(),'Preregistration already exists; do not overwrite'
    decoded=json.loads((ROOT/'research/nr7-history-chunk1-decoded.json').read_text())
    assert {r['date'] for r in decoded}=={'2026-09-23','2026-09-24','2026-09-25'}
    native=json.loads((ROOT/'research/nr7-existing-minute-audit.json').read_text())
    old=json.loads((ROOT/'research/nr7-rth-coverage.json').read_text())
    warm=sorted(decoded+native['sessions'],key=lambda r:r['date'])
    evaluation=[r for r in old['sessions'] if r['date']<='2026-10-12']
    assert len(warm)==len(evaluation)==7
    sessions=[];closes={};sources=[]
    for r in warm+evaluation:
        day=r['date']
        if sessions:
            expected=date.fromisoformat(sessions[-1]['date'])+timedelta(days=1)
            while expected.weekday()>4:expected+=timedelta(days=1)
            assert day==expected.isoformat(),'Missing actual session; cannot skip gap'
        row={k:r[k] for k in ('date','high','low','close')};row['range']=row['high']-row['low'];sessions.append(row)
        if r in warm:
            assert r['rth_minutes']==390 and [b['minute'] for b in r['bars']]==list(range(570,960))
            closes[day]={str(b['minute']):b['close'] for b in r['bars']}
            sources.append(dict(date=day,source=r['source'],independent_tick_crosscheck=r.get('integrity_passed',False),sha256=r.get('nrd_sha256')))
        else:
            closes[day]=old['minute_closes'][day]
            sources.extend(s for s in old['sources'] if s['date']==day)
    setups=[]
    for i in range(7,14):
        prior=sessions[i-7:i]
        setups.append(dict(date=sessions[i]['date'],prior_dates=[r['date'] for r in prior],qualified=prior[-1]['range']>0 and all(prior[-1]['range']<r['range'] for r in prior[:-1]),prior_high=prior[-1]['high'],prior_low=prior[-1]['low'],prior_date=prior[-1]['date']))
    audit=dict(complete=True,sessions=sessions,setups=setups,minute_closes=closes,sources=sources,source_report_hashes={p:file_hash(ROOT/'research'/p) for p in ['nr7-history-chunk1-decoded.json','nr7-existing-minute-audit.json','nr7-rth-coverage.json']},role='7warmup and7distinct historical evaluation sessions;not independent OOS',native_runs=0,timezone='America/New_York',session='09:30 inclusive to16:00 exclusive;390minutes',limitation='Sep28-Oct1 minute data are native-source audited but not independently raw-tick reconciled; observed timestamps do not prove lossless exchange capture.')
    atomic(ROOT/'research/nr7-history-extension-coverage.json',audit)
    m=json.loads((ROOT/'research/nr7-rth-manifest.json').read_text());m['created_at']=time.time();m['version']=2
    w=[r['date'] for r in warm];e=[r['date'] for r in evaluation]
    m['chronological_split'].update(warmup=w,evaluation=e,policy='7complete consecutive prior RTHsessions;7new-to-NR7 historical evaluation sessions;other candidates already used these dates;not OOS')
    m['data_requirements'].update(all_context_dates=w+e,warmup_dates=w,recent=e,recent_request_from='2026-09-22',recent_request_to='2026-10-13',type='3decoded NRD Last sessions+4native-minute audited sessions warmup;existing audited rawLast evaluation;HighTick1 native fills')
    n=sum(s['qualified'] for s in setups)
    m['coverage_conditional_budget'].update(raw_qualified_sessions=n,planned_native_runs=2 if n else 1,recorded_before_native=time.time())
    m['coverage_policy']['uncertainty']='Short/concentrated historical sample remains deferred; negative cost result misses adoption gate, not family rejection'
    m['prior_manifest_sha256']=file_hash(ROOT/'research/nr7-rth-manifest.json');m['rules_changed']=False
    validate_manifest(m);atomic(target,m)
    original=(ROOT/'native/CodexNr7Rth.cs').read_text()
    changed=original.replace('CodexNr7Rth','CodexNr7RthExtension').replace('CodexNr7Math','CodexNr7ExtensionMath').replace('date<20261002','date<20260923')
    assert changed.replace('CodexNr7RthExtension','CodexNr7Rth').replace('CodexNr7ExtensionMath','CodexNr7Math').replace('date<20260923','date<20261002')==original
    (ROOT/'native/CodexNr7RthExtension.cs').write_text(changed)
    print(json.dumps(dict(context_sessions=14,evaluation=e,qualified=[s['date'] for s in setups if s['qualified']],maximum_runs=2,planned_runs=2 if n else 1)))

if __name__=='__main__':main()
