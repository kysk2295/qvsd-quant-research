import json
from .ofi_cycle import OfiCycle
from .core import ROOT,file_hash

class Oct5(OfiCycle):
    strategy='CodexQuoteOfiOct5';coverage_report_name='ofi-oct5-coverage.json'
    def __init__(self):super().__init__('oct5')
    def validate_native(self,doc):
        c=json.loads((ROOT/'research'/self.coverage_report_name).read_text());assert file_hash(c['path'])==c['sha256']
        assert f"FEATURE_HASH {c['sha256']} rows=390" in doc['output']
        assert not any('missing_feature=' in x for x in doc['output'] if x.startswith('COUNTS '))
        n=len(doc['trades']);assert len([x for x in doc['output'] if x.startswith('CLOCK_EXEC|')])==2*n
        assert len([x for x in doc['output'] if x.startswith('CLOCK_TRADE|')])==n

if __name__=='__main__':
    c=Oct5()
    try:c.run()
    except Exception as e:c.lifecycle.update('failed',str(e),None);raise
    c.lifecycle.update('reviewing','Oct5 two fixed OFI native runs completed; auditing causal exclusion and precise simulated ledgers',None)
