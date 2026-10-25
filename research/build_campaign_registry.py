"""Reconstruct available trial lineage without claiming retrospective preregistration."""
import csv,json,time,hashlib
from datetime import date,timedelta
from collections import Counter
from runner.core import ROOT,atomic,file_hash,Queue,canonical

def main():
    out=ROOT/'research/campaign-trial-registry.json';assert not (ROOT/'research/bollinger-prospective-plan.json').exists(),'Frozen campaign cannot be silently rebuilt'
    records={};doc_map={};queue=Queue()
    def add(rid,values,source):
        row=records.setdefault(rid,dict(id=rid,evidence=[]));row.update(values)
        if source not in row['evidence']:row['evidence'].append(source)
    folders=[ROOT.parent/'qvsd-dashboard-agent/data/telemetry',queue.telemetry]
    for folder in folders:
        for p in sorted(folder.glob('*.json')):
            r=json.loads(p.read_text());params=r.get('params',{})
            add(r['id'],dict(strategy=r.get('strategy'),symbol=r.get('symbol'),batch=r.get('batch'),status=r.get('status'),phase=r.get('phase'),parameters=params.get('inputs',params),data_hash=r.get('data_hash'),metrics=r.get('metrics'),native_id=params.get('native_job_id'),source_hash=params.get('source_hash',params.get('code_hash')),manifest_hash=params.get('manifest_hash'),diagnostic_only=params.get('assessment',{}).get('diagnostic_only',False),data_role='observed_development_or_diagnostic_not_independent_oos'),dict(path=str(p),sha256=file_hash(p),kind='telemetry'))
    telemetry_count=len(records)
    seed=ROOT/'dashboard/baseline.json';baseline=json.loads(seed.read_text())
    for r in baseline:
        add(r['id'],dict(strategy=r.get('strategy'),symbol=r.get('symbol'),status=r.get('status'),batch=r.get('batch'),parameters=r.get('params'),metrics=r.get('metrics'),data_role='archived_development_baseline_not_independent_sample'),dict(path=str(seed),sha256=file_hash(seed),kind='dashboard_seed_archive'))
    for r in queue.rows():
        spec=json.loads(r['spec']);add(r['id'],dict(strategy=spec['strategy'],symbol=spec['symbol'],status=r['status'],engine=spec['engine'],queue_attempt_counter=r['attempts'],native_id=r['nt_id'],request=spec.get('request'),parameters=spec['params'],source_hash=spec['code_hash'],data_hash=spec['data_hash'],selected_dates={k:v for k,v in spec['params'].items() if k in ('from','to','from_date','to_date')},blocked_reason=r['reason'] if r['status']=='blocked' else None),dict(path=str(queue.db),row_id=r['id'],kind='queue_attempt'))
    states=[];selection=[]
    for p in sorted((ROOT/'data/runner').glob('*/state.json')):
        s=json.loads(p.read_text());states.extend((p,key,r) for key,r in s.get('experiments',{}).items())
        if 'native_id' in s:states.append((p,s.get('key','data-audit'),s))
        if s.get('selected') is not None:selection.append(dict(path=str(p),selected=s['selected'],note='Recordedhistoricalselection;not retroactively preregistered'))
    for p in sorted((ROOT/'data/runner/cafe-extension').glob('*.json')):
        s=json.loads(p.read_text())
        if 'request' in s:states.append((p,s.get('key',p.stem),s))
    for p,key,r in states:
        rid=r.get('run_id') or ('doji-'+key[:24] if p.parent.name=='doji-cycle' else 'local-attempt-'+key)
        request=r.get('request',{});doc=r.get('doc',{})
        if doc:doc_map[hashlib.sha256(canonical(doc).encode()).hexdigest()]=rid
        add(rid,dict(strategy=request.get('strategy',doc.get('strategy')),symbol='NQ',engine='native',native_id=r.get('native_id'),state=r.get('state'),ack=r.get('ack',False),request=request,parameters=request.get('inputs'),source_hash=r.get('source_hash'),data_hash=r.get('data_hash'),manifest_hash=r.get('manifest_hash'),supersedes=r.get('supersedes'),quality_correction=r.get('quality_correction'),native_error=doc.get('error'),native_state=doc.get('state'),trades=len(doc.get('trades',[])),assessment=r.get('assessment'),diagnostic_only='nr7-existing-minute-audit' in str(p) or 'execution-clock' in str(p)),dict(path=str(p),sha256=file_hash(p),key=key,kind='native_attempt'))
    rawpaths=list((ROOT/'data/runner').glob('*.native.json'))+[ROOT/'data/runner'/name for name in ('cafe-development-20261025.json','cafe-recent-20261025.json','cafe-high-resolution-20261025.json','native-scalpers-20261006.json','public-orb-batch1.json','close-momentum-batch2.json')]
    orphan=[]
    for p in rawpaths:
        x=json.loads(p.read_text());docs=x if isinstance(x,list) else [x]
        for doc in docs:
            if not isinstance(doc,dict) or not doc.get('id') or not doc.get('strategy'):continue
            nid=doc['id'];rid=doc_map.get(hashlib.sha256(canonical(doc).encode()).hexdigest())
            root_id=p.name.removesuffix('.native.json')
            if not rid and root_id in records:rid=root_id
            if not rid:
                # Legacy reporter IDs derive from complete document identity.
                possible='cafe-native-'+hashlib.sha256(json.dumps(doc,sort_keys=True).encode()).hexdigest()[:24]
                identity={k:doc[k] for k in ['strategy','inputs','startedAt','finishedAt','settings','trades']}
                legacy='native-audit-'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24]
                rid=possible if possible in records else legacy if legacy in records else 'unlinked-native-'+hashlib.sha256(canonical(doc).encode()).hexdigest()[:24]
                if rid.startswith('unlinked-'):orphan.append(nid)
            if rid in records:assert records[rid].get('strategy')==doc['strategy'],'Native IDs can repeat across assembly lifetimes;never join on native ID alone'
            add(rid,dict(strategy=doc['strategy'],symbol='NQ',native_id=nid,native_state=doc['state'],native_error=doc.get('error'),parameters=doc.get('inputs'),native_settings=doc.get('settings'),trades=len(doc.get('trades',[])),observed_loaded_range=[doc.get('barsFrom'),doc.get('barsTo')]),dict(path=str(p),sha256=file_hash(p),kind='native_document'))
    manifests=[]
    for p in sorted((ROOT/'research').glob('*manifest*.json')):
        x=json.loads(p.read_text());manifests.append(dict(path=str(p.relative_to(ROOT)),sha256=file_hash(p),definition_hash=hashlib.sha256(canonical(x).encode()).hexdigest(),search_budget=x.get('search_budget') if isinstance(x,dict) else None,chronological_split=x.get('chronological_split') if isinstance(x,dict) else None))
    for row in records.values():row['linked_manifests']=[m['path'] for m in manifests if row.get('manifest_hash')==m['definition_hash']]
    dates=set();date_sources=[]
    for p in sorted((ROOT/'research').glob('NQ_*_daily.csv')):
        ds={r['date'] for r in csv.DictReader(p.open())};dates|=ds;date_sources.append(dict(path=str(p.relative_to(ROOT)),sha256=file_hash(p),first=min(ds),last=max(ds),sessions=len(ds)))
    old=json.loads((ROOT/'research/data-role-registry.json').read_text());dates.update(old['known_observed_dates']);dates.update(old.get('warmup_context_dates',[]))
    for r in json.loads((ROOT/'research/nr7-history-chunk1-decoded.json').read_text()):dates.add(r['date'])
    earliest=min(dates);latest=max(dates)
    ledger=dict(version=1,created_at=time.time(),scope='Locallyrecoverable NQresearch plus legacy crossasset context;not universalhistory guarantee',telemetry_records=telemetry_count,queue_records=len(queue.rows()),records=list(records.values()),manifest_inventory=manifests,selection_events=selection+[dict(path='research/cafe-frozen-selection-20261025.json',sha256=file_hash(ROOT/'research/cafe-frozen-selection-20261025.json')),dict(path='research/candidate-backlog.json',note='Sequential analyst selection of differentfamilies on reused dates is modelselection;exact historical candidateproposal times andall humanrejectedideas not fully recoverable')],unlinked_native_documents=sorted(set(orphan)),external_dashboard_count_reported=206,external_count_gap=206-telemetry_count,external_count_gap_note='Supervisor reported206dashboardrows;194localtelemetry identities recovered. Extra remote rows not reconciled;do not equate dashboardrowcount with trials or claim complete remote audit.',observed_dates=sorted(dates),date_sources=date_sources,conservative_no_oos_interval=dict(first=earliest,last=latest,reason='Legacy public-price exploration already exposed the interval;all dates inside embargoed from pristineOOS claims'),multiple_testing_note='All candidatefamilies,paramvariants,cost/fill settings,datarepairs anddateextensions are part of selection;not independent samples. No posthoc significance claim or reconstructed preregistration.')
    ledger.update(archived_dashboard_seed_records=len(baseline),external_count_gap=206-telemetry_count-len(baseline),external_count_gap_note='Recovered194telemetry+12archivedseed identities,matching supervisor206rowcount;not a fresh remote database fetch. Seed/proxy/costrecords can share observations;206rows are not206independent tests.')
    atomic(out,ledger)
    old.setdefault('history',[]).append(dict(recorded_at=time.time(),known_observed_dates=old['known_observed_dates'],independent_oos_dates=old['independent_oos_dates'],note=old.get('note')))
    old.update(version=2,known_observed_dates=sorted(dates),independent_oos_dates=[],conservative_development_interval=ledger['conservative_no_oos_interval'],campaign_registry='research/campaign-trial-registry.json',note='All observed sources andsame-date strategyselection belongtodevelopment;reservedfuture dates are not completedOOS')
    atomic(ROOT/'research/data-role-registry.json',old)
    print(json.dumps(dict(records=len(records),localtelemetry=telemetry_count,queue=len(queue.rows()),unlinked_native=len(set(orphan)),observed_dates=len(dates),first=earliest,last=latest,strategies=dict(Counter(r.get('strategy') for r in records.values())))),flush=True)

if __name__=='__main__':main()
