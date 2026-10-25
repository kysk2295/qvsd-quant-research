import itertools,unittest
import numpy as np
from research.last_equity_bounds import FillWindow,audit_path,drawdown

class EquityBoundsTests(unittest.TestCase):
    def test_known_hold_drawdown_and_fee(self):
        r=audit_path(range(8),[100,100,110,90,105,105,105,105],[FillWindow(1,1,5,5,100,105,1)],10,1000,1)
        self.assertEqual(r['final_equity'],995)
        self.assertEqual(r['closed_trade_drawdown'],5)
        self.assertEqual(r['holding_path_drawdown_lower'],20)
        self.assertGreaterEqual(r['holding_path_drawdown_upper'],20)
    def test_short_mirror(self):
        a=audit_path(range(8),[100,100,110,90,105,105,105,105],[FillWindow(1,1,5,5,100,105,1)],10,1000,1)
        b=audit_path(range(8),[100,100,90,110,95,95,95,95],[FillWindow(1,1,5,5,100,95,-1)],10,1000,1)
        for key in ('net','holding_path_drawdown_lower','holding_path_drawdown_upper'):self.assertEqual(a[key],b[key])
    def test_encloses_enumerated_unknown_fill_positions(self):
        px=np.array([100,104,97,108,91,103,106,99,100,100.]);ts=np.arange(10)
        r=audit_path(ts,px,[FillWindow(1,3,6,8,100,103,1)],2,1000,1)
        for entry,exit in itertools.product(np.linspace(1,3,9),np.linspace(6,8,9)):
            values=[1000.]
            events=sorted(set(list(ts)+[entry,exit]))
            for at in events:
                price=px[np.searchsorted(ts,at,'right')-1]
                if at<entry:v=1000.
                elif at<exit:v=1000+price-100-1
                else:v=1001.
                values.append(v)
            dd=drawdown(values)
            self.assertLessEqual(r['holding_path_drawdown_lower'],dd+1e-8)
            self.assertGreaterEqual(r['holding_path_drawdown_upper']+1e-8,dd)
    def test_narrower_times_cannot_widen_bounds(self):
        prices=[100,101,95,104,90,108,98,105,105,105]
        broad=audit_path(range(10),prices,[FillWindow(1,3,6,8,100,105,1)],2,1000,1)
        narrow=audit_path(range(10),prices,[FillWindow(2,2,7,7,100,105,1)],2,1000,1)
        self.assertGreaterEqual(narrow['holding_path_drawdown_lower'],broad['holding_path_drawdown_lower'])
        self.assertLessEqual(narrow['holding_path_drawdown_upper'],broad['holding_path_drawdown_upper'])
    def test_equal_timestamp_order_remains_uncertain(self):
        r=audit_path([0,1,1,2,3,4,5],[100,100,120,100,80,100,100],[FillWindow(1,1,4,4,100,100,1)],0,1000,1)
        self.assertGreater(r['holding_path_drawdown_upper'],r['holding_path_drawdown_lower'])
    def test_empty_trades_flat(self):
        r=audit_path([0,1],[100,100],[],5)
        self.assertEqual(r['net'],0);self.assertEqual(r['holding_path_drawdown_upper'],0)
    def test_missing_context_rejected(self):
        with self.assertRaises(ValueError):audit_path([1,2,3],[100]*3,[FillWindow(1,1,2,2,100,100,1)],0)
    def test_overlapping_trade_windows_rejected(self):
        with self.assertRaises(ValueError):audit_path(range(10),[100]*10,[FillWindow(1,2,4,5,100,100,1),FillWindow(5,6,7,8,100,100,1)],0)
    def test_closed_drawdown_is_lower_bound(self):
        r=audit_path(range(12),[100]*12,[FillWindow(1,2,3,4,100,98,1),FillWindow(6,7,8,9,100,99,1)],2,1000,1)
        self.assertEqual(r['closed_trade_drawdown'],7)
        self.assertGreaterEqual(r['holding_path_drawdown_lower'],7)

if __name__=='__main__':unittest.main()
