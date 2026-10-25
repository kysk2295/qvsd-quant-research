import json,math
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from .rsi_cycle import RsiCycle
from .core import ROOT,ProcessLock,atomic,file_hash

class StochasticCycle(RsiCycle):
    strategy='CodexStochasticFast';parameter='KLength';bars_value=1;rth_bars=390;requires_eth=False
    manifest_name='stochastic-manifest.json';folder_name='stochastic';result_name='stochastic-results.json';id_prefix='stochastic-';batch='stochastic-fast-v1';coverage_report_name='stochastic-coverage.json'
    def validate_native(self,doc):
        coverage=json.loads((ROOT/'research'/self.coverage_report_name).read_text());seen=set();expected={};day=None;history=[];ks=[];k=d=float('nan')
        for line in doc['output']:
            if not line.startswith('STOCH '):continue
            parts=line.split();stamp=datetime.fromisoformat(parts[1]);start=stamp-timedelta(minutes=1);date=start.date().isoformat();minute=start.hour*60+start.minute;v=dict(p.split('=',1) for p in parts[2:]);bar=coverage['sessions'][date][str(minute)]
            assert (date,minute) not in seen;seen.add((date,minute))
            for name in ('high','low','close'):assert float(v[name])==bar[name]
            if date!=day:day=date;history=[];ks=[];k=d=float('nan')
            pk,pd=k,d;history.append(bar);window=history[-14:]
            high=max(b['high'] for b in window);low=min(b['low'] for b in window)
            k=100*(bar['close']-low)/(high-low) if len(window)==14 and high>low else float('nan')
            if math.isnan(k):ks=[]
            else:ks.append(k);ks=ks[-3:]
            d=sum(ks)/3 if len(ks)==3 else float('nan')
            side=1 if pk<=pd and k>d and k<20 else -1 if pk>=pd and k<d and k>80 else 0
            for name,value in [('k',k),('d',d)]:assert (math.isnan(value) and math.isnan(float(v[name]))) or abs(float(v[name])-value)<1e-8
            assert int(v['side'])==side;expected[parts[1]]=dict(side=side,close=bar['close'],k=k,d=d)
        assert seen=={(day,int(minute)) for day,bars in coverage['sessions'].items() for minute in bars}
        signals=[x for x in doc['output'] if x.startswith('SIGNAL ')];assert len(signals)==len(doc['trades'])
        counts={}
        for signal,trade in zip(signals,doc['trades']):
            parts=signal.split();stamp=datetime.fromisoformat(parts[1]).replace(tzinfo=ZoneInfo('America/New_York'));v=dict(p.split('=',1) for p in parts[2:]);e=expected[parts[1]]
            side=1 if v['side']=='L' else -1;assert e['side']==side and e['side']!=0
            for name in ('close','k','d'):assert abs(float(v[name])-e[name])<1e-8
            assert 590<=stamp.hour*60+stamp.minute<=925
            entry=datetime.fromisoformat(trade['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
            exit=datetime.fromisoformat(trade['exitTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
            assert 0<=(entry-stamp).total_seconds()<60 and entry<=exit and entry.date()==exit.date() and exit.hour*60+exit.minute<=956
            assert trade['qty']==1 and trade['side']==('Long' if side==1 else 'Short') and trade['entryName']==v['side']
            assert abs(trade['pnl']-(trade['exitPrice']-trade['entryPrice'])*20*side)<1e-6
            date=entry.date().isoformat();counts[date]=counts.get(date,0)+1;assert counts[date]<=4
        assert len([x for x in doc['output'] if x.startswith('CLOCK_EXEC|')])==2*len(doc['trades'])
    def run(self):
        with ProcessLock(self.folder/'cycle.lock'):
            assert file_hash(ROOT/'research'/self.coverage_report_name)==self.manifest['coverage_sha256']
            rows=[]
            for slip in (2,4):
                r=self.run_one('recent',14,slip);rows.append(r)
                if r['assessment']['decision']=='execution_error':break
                if not r['doc']['trades'] and not any(s.startswith('SIGNAL ') for s in r['doc']['output']):break
            atomic(ROOT/'research'/self.result_name,[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows])
            assert all(r['assessment']['decision']!='execution_error' for r in rows)

if __name__=='__main__':
    c=StochasticCycle()
    try:c.run()
    except Exception as e:c.lifecycle.update('failed',str(e),None);raise
    c.lifecycle.update('reviewing','Stochastic finite native batch ACKed;reviewing costs and clocks',None)
