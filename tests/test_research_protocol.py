import json,tempfile,unittest
from pathlib import Path
from runner.assessment import assess,ledger_evidence
from runner.research_protocol import validate_manifest,enqueue_extension

class ResearchProtocolTests(unittest.TestCase):
    def test_positive_small_sample_and_concentration(self):
        trades=[dict(pnl=110,qty=1,exitTime='2026-10-16T23:00:00'),dict(pnl=-20,qty=1,exitTime='2026-10-16T23:30:00')]
        self.assertEqual(assess(trades,5,30)['decision'],'deferred')
        evidence=ledger_evidence(trades,5)
        self.assertEqual(evidence['net_without_best_positive'],-25)
        self.assertEqual(evidence['daily_net'],{'2026-10-16':80})
        self.assertIsNone(evidence['unrealized_drawdown'])
    def test_no_trades_is_not_performance_failure(self):
        self.assertEqual(assess([],5,30,signals=3,condition_rejected=3)['decision'],'condition_mismatch')
        self.assertEqual(assess([],5,30)['decision'],'deferred')
    def test_extension_queue_is_idempotent_and_ordered(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'queue.json';review={'decision':'deferred','reason':'coverage'}
            enqueue_extension(p,'rare',review,'hash');enqueue_extension(p,'rare',review,'hash')
            tasks=json.loads(p.read_text())['tasks']
            self.assertEqual(len(tasks),3)
            self.assertEqual(tasks[1]['depends_on'],tasks[0]['id'])
            self.assertEqual(tasks[2]['depends_on'],tasks[1]['id'])
    def test_missing_manifest_rejected(self):
        with self.assertRaises(ValueError):validate_manifest({'source':'test'})

if __name__=='__main__':unittest.main()
