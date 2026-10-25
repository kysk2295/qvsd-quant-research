import json
from .ofi_cycle import OfiCycle
from .core import ROOT,file_hash

class Oct6(OfiCycle):
    strategy='CodexQuoteOfiOct6'
    coverage_report_name='ofi-oct6-coverage.json'
    def __init__(self):super().__init__('oct6')
    def validate_native(self,doc):
        c=json.loads((ROOT/'research'/self.coverage_report_name).read_text())
        assert file_hash(c['path'])==c['sha256']
        assert f"FEATURE_HASH {c['sha256']} rows=390" in doc['output']
        assert not any('missing_feature=' in x for x in doc['output'] if x.startswith('COUNTS '))

if __name__=='__main__':
    c=Oct6()
    try:c.run()
    except Exception as e:c.lifecycle.update('failed',str(e),None);raise
    c.lifecycle.update('reviewing','Oct6 two historical-extension native runs completed; auditing ledgers',None)
