import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from runner.adapter import Bridge

class CampaignGateTests(unittest.TestCase):
    def test_frozen_request_never_reaches_network(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'research').mkdir();(root/'research/campaign-search-control.json').write_text(json.dumps({'native_submission_mode':'frozen_pending_prospective_release'}))
            with patch('runner.campaign_gate.ROOT',root),patch('runner.adapter.urlopen') as network:
                with self.assertRaisesRegex(RuntimeError,'budget frozen'):Bridge().call('POST','/backtest',{'strategy':'CodexBollingerClock'})
                network.assert_not_called()
    def test_label_change_does_not_bypass_counted_packet(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'research').mkdir();(root/'research/campaign-search-control.json').write_text(json.dumps({'native_submission_mode':'released_finite_packet'}))
            with patch('runner.campaign_gate.ROOT',root),patch('runner.adapter.urlopen') as network:
                with self.assertRaisesRegex(RuntimeError,'not released'):Bridge().call('POST','/backtest',{})
                network.assert_not_called()
    def test_read_only_monitor_remains_available(self):
        with patch('runner.adapter.ensure_native_submission_allowed',create=True) as gate,patch('runner.adapter.urlopen') as network:
            network.return_value.__enter__.return_value.read.return_value=b'{"ok":true}'
            self.assertEqual(Bridge().call('GET','/health'),{'ok':True});gate.assert_not_called()
    def test_order_endpoint_stays_outside_allowlist(self):
        with patch('runner.adapter.urlopen') as network:
            with self.assertRaises(ValueError):Bridge().call('POST','/orders',{})
            network.assert_not_called()

if __name__=='__main__':unittest.main()
