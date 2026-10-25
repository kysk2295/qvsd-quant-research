import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from .core import Queue, ProcessLock, dataset_hash
from .worker import Worker
from .adapter import native_result

class Fake:
    def __init__(self):self.calls=[];self.doc={'state':'running'};self.fail_submit=False;self.fail_cancel=False
    def call(self,method,path,body=None):
        self.calls.append((method,path))
        if path=='/health':return dict(ok=True,startedAt='instance1')
        if path=='/backtests':return []
        if method=='POST':
            if self.fail_submit:raise TimeoutError()
            return {'id':'b123'}
        if method=='DELETE':
            if self.fail_cancel:raise TimeoutError()
            return {'ok':True}
        return self.doc

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        f=self.root/'fixture';f.write_text('test');h=dataset_hash([f])
        self.s=dict(engine='nt',symbol='NQ',strategy='SampleMACrossOver',dataset='test',data_hash=h,
          files=[str(f)],code_files=[str(f)],code_hash=h,code_commit='test',params={},timeout_s=2,max_preflight_retries=1,
          cost=dict(label='test',slippage_ticks=2,round_trip_fee=5),request=dict(strategy='SampleMACrossOver',instrument='NQ 12-26',
          barsPeriod=dict(type='Minute',value=5),inputs=dict(Fast=10,Slow=25),tickReplay=False,fillResolution='Standard',
          includeCommission=False,includeTradeHistory=True,slippageTicks=2))
        self.q=Queue(self.root/'q',self.root/'telemetry');self.b=Fake();self.w=Worker(self.q,self.b)
    def tearDown(self):self.tmp.cleanup()
    def start(self):
        jid=self.q.enqueue(self.s);self.q.control('mode','running');self.w.tick();return jid
    def test_dedupe_persistence_single_claim(self):
        jid=self.q.enqueue(self.s);self.assertEqual(jid,self.q.enqueue(copy.deepcopy(self.s)))
        q2=Queue(self.q.folder,self.q.telemetry);self.assertEqual(len(q2.rows()),1)
        self.q.control('mode','running');self.assertEqual(self.q.claim(),jid);self.assertIsNone(q2.claim())
    def test_pause_resume(self):
        jid=self.q.enqueue(self.s);self.w.tick();self.assertEqual(self.q.get(jid)['status'],'queued')
        self.q.control('mode','running');self.w.tick();self.assertEqual(self.q.get(jid)['nt_id'],'b123')
    def test_known_native_recovery_never_resubmits(self):
        jid=self.start();Worker(Queue(self.q.folder,self.q.telemetry),self.b).tick()
        self.assertEqual(self.b.calls.count(('POST','/backtest')),1)
        self.assertEqual(self.q.get(jid)['status'],'running')
    def test_ambiguous_submission_latches_pause(self):
        self.b.fail_submit=True;jid=self.start();self.w.tick()
        self.assertTrue(self.q.control('uncertain'));self.assertEqual(self.q.control('mode'),'paused')
        self.assertEqual(self.b.calls.count(('POST','/backtest')),1)
    def test_crash_after_write_ahead_intent(self):
        jid=self.q.enqueue(self.s);self.q.control('mode','running');self.q.claim()
        self.q.update(jid,phase='submitting');self.w.tick()
        self.assertEqual(self.q.get(jid)['status'],'blocked');self.assertFalse(self.b.calls)
    def test_timeout_cancels_own_job_only(self):
        jid=self.start();self.q.update(jid,deadline=time.time()-1);self.w.tick()
        self.assertIn(('DELETE','/backtest/b123'),self.b.calls);self.assertEqual(self.q.get(jid)['status'],'failed')
    def test_unconfirmed_cancel_stops_queue(self):
        jid=self.start();self.b.fail_cancel=True;self.q.update(jid,deadline=0);self.w.tick()
        self.assertEqual(self.q.control('mode'),'paused');self.assertTrue(self.q.control('uncertain'))
    def test_stop_cancels(self):
        jid=self.start();self.q.control('mode','stopped');self.w.tick()
        self.assertEqual(self.q.get(jid)['status'],'failed');self.assertIsNone(self.q.claim())
    def test_preflight_retries_bounded(self):
        jid=self.q.enqueue(self.s)
        self.q.block(jid,'offline',retry=True);self.assertEqual(self.q.get(jid)['status'],'queued')
        self.q.block(jid,'offline',retry=True);self.assertEqual(self.q.get(jid)['status'],'blocked')
    def test_lock(self):
        with ProcessLock(self.root/'lock'):
            with self.assertRaises(RuntimeError):
                with ProcessLock(self.root/'lock'):pass
    def test_telemetry_all_statuses_schema_and_identity(self):
        from dashboard.server import validate_run
        jid=self.q.enqueue(self.s)
        for status in ('queued','running','completed','failed','rejected','blocked'):
            self.q.update(jid,status=status)
            snap=json.loads(next(self.q.telemetry.glob('*.json')).read_text(encoding='utf-8'))
            self.assertEqual(validate_run(snap)['status'],status)
            self.assertEqual(snap['worker'],'windows-experiment-runner')
    def test_native_cost_reconstruction_and_readback(self):
        doc=dict(settings={'slippageTicks':2,'includeCommission':False,'fillResolution':'Standard','includeTradeHistory':True},summary={'trades':2},trades=[
          dict(pnl=100,qty=2,exitTime='a'),dict(pnl=-50,qty=1,exitTime='b')])
        r=native_result(doc,self.s);self.assertEqual(r['metrics']['net'],35)
        self.assertEqual(r['metrics']['closed_trade_mdd'],55)
        doc['settings']['slippageTicks']=0
        with self.assertRaises(ValueError):native_result(doc,self.s)
    def test_coverage_mismatch_blocks_following_native_case(self):
        jid=self.q.enqueue(self.s);s2=copy.deepcopy(self.s);s2['params']['other']=1
        other=self.q.enqueue(s2)
        self.w.finish(jid,dict(metrics={},equity=[],rejected=True,coverage_invalid=True,reason='mismatch'))
        self.assertEqual(self.q.get(jid)['status'],'rejected')
        self.assertEqual(self.q.get(other)['status'],'blocked')
    def test_exact_observed_window_reproduction_is_separate(self):
        s=copy.deepcopy(self.s);s['params']['expected_bars']={'from':'2026-09-30T07:05:00','to':'2026-10-02T13:00:00'}
        s['request'].update(s['params']['expected_bars'])
        doc=dict(settings={'slippageTicks':2,'includeCommission':False,'fillResolution':'Standard','includeTradeHistory':True},
                 summary={'trades':0},trades=[],barsFrom=s['request']['from'],barsTo=s['request']['to'],
                 warnings=['Playback warning uses Eastern clock against NT local clock'])
        self.assertFalse(native_result(doc,s)['coverage_invalid'])
        doc['barsTo']='2026-10-01T13:00:00'
        self.assertTrue(native_result(doc,s)['coverage_invalid'])
    def test_missing_native_window_is_rejected(self):
        doc=dict(settings={'slippageTicks':2,'includeCommission':False,'fillResolution':'Standard','includeTradeHistory':True},summary={'trades':0},trades=[])
        self.assertTrue(native_result(doc,self.s)['rejected'])
    def test_changed_data_blocks_before_submit(self):
        Path(self.s['files'][0]).write_text('changed');jid=self.start()
        self.assertEqual(self.q.get(jid)['status'],'blocked');self.assertFalse(self.b.calls)

if __name__=='__main__':unittest.main()
