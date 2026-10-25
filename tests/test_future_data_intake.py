import json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from runner.core import file_hash
from runner.future_data_intake import FutureIntake

class FutureDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'research').mkdir();self.download=self.root/'download';self.download.mkdir()
        dates=['2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-11-02']
        (self.root/'research/bollinger-prospective-plan.json').write_text(json.dumps({'evaluation_dates':dates}))
        self.intake=FutureIntake(self.root,self.download);self.intake.initialize()
    def tearDown(self):self.tmp.cleanup()
    def test_preclose_is_ineligible(self):
        self.assertEqual(self.intake.available(datetime(2026,10,26,19,59,tzinfo=timezone.utc))['eligible_dates'],[])
    def test_dst_changes_close_utc(self):
        e=self.intake.load()['entries'];self.assertIn('20:00:00',e['2026-10-26']['session_close_utc']);self.assertIn('21:00:00',e['2026-11-02']['session_close_utc'])
    def test_three_date_batch_and_repeat_prevention(self):
        now=datetime(2026,11,3,tzinfo=timezone.utc);dates=self.intake.available(now)['eligible_dates'];self.assertEqual(len(dates),3)
        token=self.intake.claim_batch(dates,now)
        with self.assertRaises(ValueError):self.intake.claim_batch([dates[0]],now)
        self.intake.record_submission(dates[0],token,now)
        with self.assertRaises(ValueError):self.intake.record_submission(dates[0],token,now)
    def test_oversized_batch_rejected(self):
        with self.assertRaises(ValueError):self.intake.claim_batch(list(self.intake.load()['entries'])[:4],datetime(2026,11,3,tzinfo=timezone.utc))
    def test_existing_file_blocks_download(self):
        (self.download/'20261026.nrd').write_bytes(b'existing')
        r=self.intake.available(datetime(2026,10,27,tzinfo=timezone.utc));self.assertIn('2026-10-26',r['existing_files_requiring_audit']);self.assertNotIn('2026-10-26',r['eligible_dates'])
    def test_uncertain_submission_consumes_budget(self):
        now=datetime(2026,10,27,tzinfo=timezone.utc);self.intake.claim_batch(['2026-10-26'],now);self.intake.record_failure('2026-10-26','transport uncertain')
        self.assertNotIn('2026-10-26',self.intake.available(now)['eligible_dates'])
    def test_quality_requires_source_hash_and_full_session(self):
        source=self.download/'20261026.nrd';source.write_bytes(b'fixture');p=self.root/'quality.json'
        audit=dict(date='2026-10-26',rth_minutes=389,integrity_passed=True,missing_minutes=[],source_sha256=file_hash(source));p.write_text(json.dumps(audit))
        with self.assertRaises(ValueError):self.intake.record_quality('2026-10-26',p)
        audit['rth_minutes']=390;p.write_text(json.dumps(audit));self.intake.record_quality('2026-10-26',p)
        self.assertEqual(self.intake.load()['entries']['2026-10-26']['status'],'quality_passed')

if __name__=='__main__':unittest.main()
