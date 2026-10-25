import unittest
from research.trade_metrics import evaluate,bootstrap_days

def trade(pnl,index=0,side='Long',mae=10,mfe=20):
    return dict(entryTime=f'2026-10-06T{22+index}:00:00',exitTime=f'2026-10-06T{22+index}:01:00',
        entryPrice=20000,exitPrice=20000+pnl/(20 if side=='Long' else -20),side=side,qty=1,pnl=pnl,mae=mae,mfe=mfe)

class MetricsTests(unittest.TestCase):
    def test_win_loss_expectancy_identity(self):
        r=evaluate([trade(200),trade(-100,1)],['2026-10-06'],10)
        self.assertEqual(r['win_rate'],.5);self.assertEqual(r['net'],80);self.assertEqual(r['expectancy_per_trade'],40)
        self.assertAlmostEqual(r['realized_payoff_ratio'],190/110);self.assertAlmostEqual(r['profit_factor'],190/110)
        self.assertEqual(r['closed_trade_drawdown']['maximum'],110)
    def test_short_symmetry(self):
        a=evaluate([trade(200)],['2026-10-06'],10);b=evaluate([trade(200,side='Short')],['2026-10-06'],10)
        self.assertEqual(a['net'],b['net']);self.assertEqual(a['excursion'],b['excursion'])
    def test_all_win_pf_undefined(self):
        r=evaluate([trade(200)],['2026-10-06'],10);self.assertIsNone(r['profit_factor']);self.assertIsNone(r['realized_payoff_ratio'])
    def test_no_trades_is_not_zero_win_rate(self):
        r=evaluate([],['2026-10-06'],10);self.assertIsNone(r['win_rate']);self.assertIsNone(r['expectancy_per_trade']);self.assertEqual(r['net'],0)
    def test_after_fee_win_changes_to_breakeven(self):
        r=evaluate([trade(10)],['2026-10-06'],10);self.assertEqual(r['breakeven'],1);self.assertEqual(r['wins'],0)
    def test_zero_sessions_in_daily_mean(self):
        r=evaluate([trade(200)],['2026-10-06','2026-10-07'],10);self.assertEqual(r['mean_daily_pnl'],95);self.assertEqual(r['trades_per_session'],.5)
    def test_extra_cost_is_two_fills_and_quantity(self):
        r=evaluate([trade(200)],['2026-10-06'],10);self.assertEqual(r['additional_cost_sensitivity'][-1]['net'],150);self.assertEqual(r['additional_ticks_per_fill_breakeven'],19)
    def test_duplicate_rejected(self):
        t=trade(200)
        with self.assertRaises(ValueError):evaluate([t,t],['2026-10-06'],10)
    def test_wrong_gross_rejected(self):
        t=trade(200);t['pnl']=300
        with self.assertRaises(ValueError):evaluate([t],['2026-10-06'],10)
    def test_wrong_date_rejected(self):
        with self.assertRaises(ValueError):evaluate([trade(200)],['2026-10-07'],10)
    def test_bad_excursions_excluded(self):
        r=evaluate([trade(200,mfe=1)],['2026-10-06'],10);self.assertEqual(r['excursion']['inconsistent'],1);self.assertIsNone(r['excursion']['mean_mfe_currency'])
    def test_nominal_R_and_missing_risk(self):
        r=evaluate([trade(-240,mae=12)],['2026-10-06'],10,48);self.assertAlmostEqual(r['mean_net_R'],-250/240)
        self.assertIsNone(evaluate([trade(200)],['2026-10-06'],10)['mean_net_R'])
    def test_bootstrap_reproducible_and_short_guard(self):
        self.assertEqual(bootstrap_days(list(range(15))),bootstrap_days(list(range(15))))
        self.assertIsNone(bootstrap_days([1,2])['interval'])
    def test_high_profit_does_not_equal_bestday_robustness(self):
        r=evaluate([trade(200),trade(-100,1)],['2026-10-06'],10)
        self.assertEqual(r['net_without_best_positive_day'],0);self.assertEqual(r['max_consecutive_losses'],1)

if __name__=='__main__':unittest.main()
