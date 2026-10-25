import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import numpy as np
from runner.core import atomic, file_hash
from runner.future_data_intake import FutureIntake
from runner.future_data_collector import Collector, quality_arrays

class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        atomic(self.root/'research/bollinger-prospective-plan.json',dict(evaluation_dates=['2026-10-26','2026-10-27','2026-10-28','2026-10-29']))
        self.intake=FutureIntake(self.root,self.root/'downloads');self.intake.initialize()
        self.adapter=Mock();self.adapter.idle.return_value=True;self.adapter.submit.return_value={'requested':True}
        self.publisher=Mock(return_value=dict(ack=True))
        def audit(day, source, folder):
            p=folder/(day+'.json');atomic(p,dict(date=day,source_sha256=file_hash(source),integrity_passed=True,rth_minutes=390,missing_minutes=[]));return p
        self.audit=Mock(side_effect=audit)
        self.collector=Collector(self.intake,self.adapter,self.audit,self.publisher)
        self.now=datetime(2026,10,30,tzinfo=timezone.utc)
    def tearDown(self):self.tmp.cleanup()
    def existing(self,day):
        p=Path(self.intake.load()['entries'][day]['expected_download_path']);p.parent.mkdir(exist_ok=True);p.write_bytes(b'fixture')
    def test_dry_run_has_no_external_calls(self):
        r=self.collector.run(self.now);self.assertTrue(r['dry_run']);self.adapter.idle.assert_not_called();self.assertEqual(self.intake.load()['actual_download_requests'],0)
    def test_preclose_no_calls_even_with_existing_file(self):
        self.existing('2026-10-26');self.collector.run(datetime(2026,10,26,19,59,tzinfo=timezone.utc),True);self.adapter.idle.assert_not_called();self.audit.assert_not_called()
    def test_reservation_persisted_before_external_call(self):
        def submit(day):
            e=self.intake.load()['entries'][day];self.assertEqual(e['status'],'submitted_awaiting_file');self.assertEqual(e['submission_budget_consumed'],1);return {'requested':True}
        self.adapter.submit.side_effect=submit
        r=self.collector.run(self.now,True);self.assertEqual(r['downloads_submitted'],1)
    def test_uncertain_date_never_resubmitted(self):
        self.adapter.submit.side_effect=TimeoutError()
        self.collector.run(self.now,True);self.collector.run(self.now,True)
        self.assertEqual([c.args[0] for c in self.adapter.submit.call_args_list],['2026-10-26','2026-10-27'])
    def test_existing_files_audited_max_three_and_ack_not_repeated(self):
        for day in self.intake.load()['entries']:self.existing(day)
        self.collector.run(self.now,True);self.assertEqual(self.publisher.call_count,3)
        self.collector.run(self.now,True);self.assertEqual(self.publisher.call_count,4);self.adapter.submit.assert_not_called()
    def test_busy_no_submission_or_decode(self):
        self.adapter.idle.return_value=False;self.collector.run(self.now,True);self.adapter.submit.assert_not_called();self.audit.assert_not_called()
    def test_quality_failure_never_published(self):
        self.existing('2026-10-26');self.audit.side_effect=ValueError('partial')
        with self.assertRaises(ValueError):self.collector.run(self.now,True)
        self.publisher.assert_not_called();self.adapter.submit.assert_not_called()
    def test_ack_failure_retains_quality_and_never_redownloads(self):
        self.existing('2026-10-26');self.publisher.side_effect=RuntimeError('ACK unavailable')
        with self.assertRaises(RuntimeError):self.collector.run(self.now,True)
        self.assertEqual(self.intake.load()['entries']['2026-10-26']['status'],'quality_passed');self.adapter.submit.assert_not_called()
    def test_changed_plan_fails(self):
        self.intake.planhash='changed'
        with self.assertRaises(AssertionError):self.collector.run(self.now,True)
        self.adapter.idle.assert_not_called()
    def test_quality_dst_missing_minute_and_order(self):
        start=int(datetime(2026,11,2,14,30,tzinfo=timezone.utc).timestamp())*10**9
        ts=start+np.arange(390,dtype=np.int64)*60*10**9;kind=np.full(390,2);price=np.full(390,20000.25);vol=np.ones(390)
        self.assertEqual(quality_arrays('2026-11-02',ts,kind,price,vol)['rth_minutes'],390)
        with self.assertRaises(ValueError):quality_arrays('2026-11-02',ts[:-1],kind[:-1],price[:-1],vol[:-1])
        with self.assertRaises(ValueError):quality_arrays('2026-11-02',ts[::-1],kind,price,vol)

if __name__=='__main__':unittest.main()
