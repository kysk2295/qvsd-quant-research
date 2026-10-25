"""Pre-execution manifests and idempotent evidence-completion work queues."""
import hashlib
from .core import atomic,canonical

REQUIRED=('source','hypothesis','rules','data_requirements','expected_frequency','metrics',
          'costs','risk','search_budget','chronological_split','coverage_policy','stop_policy')

def validate_manifest(manifest):
    missing=[k for k in REQUIRED if not manifest.get(k)]
    if missing:raise ValueError('Research manifest missing: '+', '.join(missing))
    if manifest['chronological_split'].get('role') not in ('development','historical_extension','prospective_validation'):
        raise ValueError('Explicit data role required')
    if not manifest['coverage_policy'].get('unit')=='session':
        raise ValueError('Dependence-aware session assessment required')
    return hashlib.sha256(canonical(manifest).encode()).hexdigest()

def enqueue_extension(path,candidate,assessment,manifest_hash):
    import json
    queue=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'version':1,'tasks':[]}
    if assessment['decision'] not in ('deferred','condition_mismatch'):return
    preceding=None
    for kind in ('data-extension','coverage-audit','re-evaluation'):
        key=hashlib.sha256(canonical([candidate,manifest_hash,kind]).encode()).hexdigest()[:24]
        if not any(t['id']==key for t in queue['tasks']):
            queue['tasks'].append(dict(id=key,candidate=candidate,kind=kind,status='pending',
                depends_on=preceding,manifest_hash=manifest_hash,reason=assessment['reason'],
                next_action='Use distinct data, frozen parameters; preserve previous trials and observed-date registry'))
        preceding=key
    atomic(path,queue)
