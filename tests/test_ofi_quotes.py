import unittest
import numpy as np
from research.ofi_quote_audit import side_contribution

class OfiQuoteTests(unittest.TestCase):
    def test_bid_events_use_queue_size_not_trades(self):
        p=np.array([100,100,101,100]);q=np.array([10,13,7,9])
        np.testing.assert_array_equal(side_contribution(p,q,1),[3,7,-7])
    def test_ask_events_have_reversed_sign(self):
        p=np.array([101,101,100,101]);q=np.array([10,13,7,9])
        np.testing.assert_array_equal(side_contribution(p,q,0),[-3,-7,7])
    def test_same_price_cancellation_and_identical_update(self):
        p=np.array([100,100,100]);q=np.array([10,4,4])
        np.testing.assert_array_equal(side_contribution(p,q,1),[-6,0])
        np.testing.assert_array_equal(side_contribution(p,q,0),[6,0])
    def test_future_suffix_cannot_change_prefix(self):
        p=np.array([100,100,101,99,200]);q=np.array([10,12,4,9,800])
        for side in (0,1):np.testing.assert_array_equal(side_contribution(p,q,side)[:2],side_contribution(p[:3],q[:3],side))
    def test_last_events_are_rejected(self):
        with self.assertRaises(ValueError):side_contribution(np.array([100,101]),np.array([10,99]),2)

if __name__=='__main__':unittest.main()
