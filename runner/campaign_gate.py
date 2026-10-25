"""Research-budget gate, not an account/order authorization mechanism."""
import json
from .core import ROOT

def ensure_native_submission_allowed():
    path=ROOT/'research/campaign-search-control.json'
    if not path.exists():return
    policy=json.loads(path.read_text())
    if policy.get('native_submission_mode')!='released_finite_packet':
        raise RuntimeError('Campaign native budget frozen: complete prospective release conditions; no new historical performance or diagnostic submission')
    # A future release must implement a specific, counted execution packet.
    # Changing a label alone cannot create a new submission allowance.
    raise RuntimeError('Prospective packet executor not released; inspect registered plan and record finite attempt before enabling submission')
