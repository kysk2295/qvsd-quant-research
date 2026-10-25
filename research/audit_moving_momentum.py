"""Audit causal setup traces against native fills and persist reproducible evidence."""
import json
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from runner.core import ROOT,atomic,file_hash

NY=ZoneInfo('America/New_York');KST=ZoneInfo('Asia/Seoul')
def eastern(value):
    return datetime.fromisoformat(value).replace(tzinfo=KST).astimezone(NY)

def audit(row):
    doc=row['doc'];assert doc['state']=='done' and not doc.get('error')
    traces=[];signals=[];armed=None;previous_bar=None;previous_day=None
    for line in doc['output']:
        if line.startswith('TRACE '):
            parts=line.split();stamp=datetime.fromisoformat(parts[1]).replace(tzinfo=NY)
            x=dict(p.split('=') for p in parts[2:]);bar=int(x['bar']);bias=int(x['bias'])
            event=x['event'];hist=float(x['hist']);prior=float(x['prior']);k=float(x['k'])
            if previous_bar is None or bar!=previous_bar+1 or stamp.date()!=previous_day:armed=None
            if event=='setup_armed':
                assert armed is None and ((bias==1 and k<20) or (bias==-1 and k>80))
                armed=(bar,bias)
            elif event=='confirmation':
                assert armed is not None and armed[1]==bias
                assert int(x['age'])==bar-armed[0] and 1<=int(x['age'])<=6
                assert (bias==1 and prior<=0<hist) or (bias==-1 and prior>=0>hist)
                signals.append(dict(time=stamp.isoformat(),side='Long' if bias==1 else 'Short',age=int(x['age'])))
                armed=None
            elif event=='setup_expired':
                assert armed is not None and bar-armed[0]>6;armed=None
            elif event=='setup_bias_invalidated':
                assert armed is not None and armed[1]!=bias;armed=None
            elif event=='await_confirmation':assert armed is not None
            elif event=='no_setup':assert armed is None
            else:raise AssertionError('Unexpected setup event '+event)
            traces.append(dict(time=stamp.isoformat(),**x));previous_bar=bar;previous_day=stamp.date()
    printed=[x for x in doc['output'] if x.startswith('SIGNAL ')]
    assert len(printed)==len(signals)==len(doc['trades']),'Unmatched signal/fill'
    matched=[];previous_exit=None;counts=Counter()
    for signal,t in zip(signals,doc['trades']):
        entry=eastern(t['entryTime']);exit=eastern(t['exitTime']);st=datetime.fromisoformat(signal['time'])
        delta=(entry-st).total_seconds()
        assert signal['side']==t['side'] and t['qty']==1
        assert 0<=delta<=300,'Fill outside next five-minute bar'
        assert exit>=entry and entry.date()==exit.date()
        assert previous_exit is None or entry>=previous_exit,'Overlapping positions'
        previous_exit=exit;counts[entry.date().isoformat()]+=1
        expected=(t['exitPrice']-t['entryPrice'])*(1 if t['side']=='Long' else -1)*20*t['qty']
        assert abs(t['pnl']-expected)<1e-6
        matched.append(dict(signal=signal,entry_et=entry.isoformat(),exit_et=exit.isoformat(),signal_to_fill_seconds=delta,trade=t))
    assert all(n<=4 for n in counts.values())
    return dict(run_id=row['run_id'],native_id=row['native_id'],trace_rows=len(traces),signals=len(signals),trades=len(matched),
        matched=matched,trace=traces,checks_passed=True,source_hash=row['source_hash'],data_hash=row['data_hash'],
        native_response_sha256=file_hash(ROOT/'data/runner/moving-momentum'/(row['key']+'.native.json')),
        limitation='Historical engine only. Timestamp tolerance is the next five-minute bar; this is not Playback fill equivalence.')

def main():
    state=json.loads((ROOT/'data/runner/moving-momentum/state.json').read_text())
    rows=sorted(state['experiments'].values(),key=lambda r:r['request']['slippageTicks'])
    reports=[audit(r) for r in rows]
    for r in reports:print(json.dumps({k:r[k] for k in ('run_id','trace_rows','signals','trades','checks_passed')}))
    atomic(ROOT/'research/moving-momentum-trace-audit.json',reports)
    same=[(t['entryTime'],t['entryPrice'],t['exitTime'],t['exitPrice'],t['qty'],t['side']) for t in rows[0]['doc']['trades']]==[(t['entryTime'],t['entryPrice'],t['exitTime'],t['exitPrice'],t['qty'],t['side']) for t in rows[1]['doc']['trades']]
    atomic(ROOT/'research/moving-momentum-native-cost-comparison.json',dict(identical_fills=same,native_requested_ticks=[2,4],
        conclusion='Actual native fill tuples compared; additional2/4tick arithmetic cost scenarios remain separate from native execution.',run_ids=[r['run_id'] for r in rows]))

if __name__=='__main__':main()
