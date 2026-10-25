from .nr7_cycle import Nr7Cycle
import json
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from .core import ROOT

class Nr7ExtensionCycle(Nr7Cycle):
    strategy='CodexNr7RthExtension'
    manifest_name='nr7-history-extension-manifest.json'
    folder_name='nr7-history-extension'
    result_name='nr7-history-extension-results.json'
    id_prefix='nr7-extension-'
    batch='nr7-history-extension-v1'
    coverage_report_name='nr7-history-extension-coverage.json'

    def validate_native(self,doc):
        super().validate_native(doc)
        coverage=json.loads((ROOT/'research'/self.coverage_report_name).read_text())
        expected=[]
        for setup in coverage['setups']:
            if not setup['qualified']:continue
            day=setup['date']
            for minute in range(570,925):
                close=coverage['minute_closes'][day][str(minute)]
                side='L' if close>=setup['prior_high']+0.25 else 'S' if close<=setup['prior_low']-0.25 else None
                if side:
                    stamp=datetime.fromisoformat(day)+timedelta(minutes=minute+1)
                    expected.append((stamp,side,close,setup));break
        signals=[line for line in doc['output'] if line.startswith('SIGNAL ')]
        assert len(signals)==len(expected)==len(doc['trades']),'Independent minute-close breakout count mismatch'
        for line,(stamp,side,close,setup),trade in zip(signals,expected,doc['trades']):
            parts=line.split();v=dict(p.split('=',1) for p in parts[2:])
            assert datetime.fromisoformat(parts[1])==stamp and v['side']==side
            assert float(v['close'])==close and float(v['high'])==setup['prior_high'] and float(v['low'])==setup['prior_low']
            entry=datetime.fromisoformat(trade['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
            exit=datetime.fromisoformat(trade['exitTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
            assert 0<=(entry-stamp.replace(tzinfo=ZoneInfo('America/New_York'))).total_seconds()<60
            assert entry<=exit and entry.date()==exit.date() and exit.hour*60+exit.minute<=956
            assert trade['entryName']==side and trade['side']==('Long' if side=='L' else 'Short') and trade['qty']==1
            sign=1 if side=='L' else -1
            assert abs(trade['pnl']-(trade['exitPrice']-trade['entryPrice'])*20*sign)<1e-6

if __name__=='__main__':
    c=Nr7ExtensionCycle()
    try:c.run()
    except Exception as e:c.lifecycle.update('failed',str(e),None);raise
    c.lifecycle.update('reviewing','Finite NR7 extension native results saved; auditing signals and ledger',None)
