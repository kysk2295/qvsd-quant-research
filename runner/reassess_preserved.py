"""Add assessment metadata to preserved Cafe results without changing terminal status or metrics."""
import hashlib,json
from .core import ROOT,Queue,atomic,file_hash
from .assessment import assess,ledger_evidence
from .research_protocol import validate_manifest,enqueue_extension
from dashboard.reporter import post

def main():
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text(encoding='utf-8'))
    changes=[];deferred=[]
    manifest=json.loads((ROOT/'research/cafe-extension-manifest.json').read_text(encoding='utf-8'))
    manifest_hash=validate_manifest(manifest)
    for phase in ('development','recent','high-resolution'):
        for d in json.loads((ROOT/'data/runner'/('cafe-'+phase+'-20261025.json')).read_text(encoding='utf-8')):
            jid='cafe-native-'+hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()[:24]
            path=q.telemetry/(hashlib.sha256(jid.encode()).hexdigest()+'.json')
            old=json.loads(path.read_text(encoding='utf-8'));run=json.loads(json.dumps(old))
            fee=5 if d['settings']['slippageTicks']==2 else 10
            rejected=sum(x.startswith('SIZE_REJECT ') for x in d['output'])
            assessment=assess(d['trades'],fee,20 if phase=='recent' else 30,signals=rejected,condition_rejected=rejected)
            assessment['ledger_evidence']=ledger_evidence(d['trades'],fee)
            for line in d['output']:
                if line.startswith('AUDIT '):
                    day=line.split()[1]
                    assessment['ledger_evidence']['daily_net'].setdefault(day[:4]+'-'+day[4:6]+'-'+day[6:8],0)
            assessment['ledger_evidence']['daily_basis']='exit date ET including audited zero-trade sessions; repeated cost/fill runs are not independent observations'
            assessment['coverage_policy']=manifest['coverage_policy']
            assessment['legacy_trade_threshold_note']='Historical gate retained for audit only; future evaluation uses frozen session coverage and uncertainty policy'
            enqueue_extension(ROOT/'research/evidence-work-queue.json',str(d['inputs']['Variant'])+'-'+str(d['inputs']['RangeMinutes']),assessment,manifest_hash)
            assessment['legacy_status_note']='Existing rejected is retained as calculation lifecycle history; use assessment.decision for research disposition'
            run.setdefault('params',{})['assessment']=assessment
            if assessment['decision']=='deferred':run['reason']='판단 보류 · 표본 부족 · 데이터 확장 후 추가 검증';deferred.append(jid)
            elif assessment['decision']=='condition_mismatch':run['reason']='조건 부적합 · 위험 한도로 거래 없음 · 전략 성과 미판정'
            else:run['reason']='현재 표본 비용 후 성과 기준 미달 · 영구 폐기 아님'
            assert run['status']==old['status'] and run['metrics']==old['metrics']
            response=post(config['url'],'/api/runs',run,config['token'])
            if response.get('ok') is not True:raise RuntimeError('No assessment ACK')
            atomic(path,run);q.control('ack:'+path.name,file_hash(path))
            changes.append(dict(id=jid,legacy_status=old['status'],assessment=assessment,metrics_preserved=True,ack=True))
    atomic(ROOT/'research/cafe-reassessment-20261025.json',changes)
    backlog=json.loads((ROOT/'research/candidate-backlog.json').read_text(encoding='utf-8'))
    cid='cafe-positive-data-extension'
    if not any(c['id']==cid for c in backlog['candidates']):
        backlog['candidates'].append(dict(id=cid,priority=10,status='awaiting_new_data',sources=['docs/nq-validation-cycle-2026-10-25.md'],
            original_rule='Preserved positive Cafe retest and failed-IB configurations',adaptation='unchanged parameters; do not re-optimize',
            data='Longer native NQ sample and future observations',run_ids=deferred,next_action='When distinct validated data arrives, evaluate frozen configurations and record new fingerprint'))
    atomic(ROOT/'research/candidate-backlog.json',backlog)
    print(json.dumps(dict(acknowledged=len(changes),deferred=len(deferred),metrics_changed=0,terminal_status_changed=0)))

if __name__=='__main__':main()
