import math
import unittest
from research.market_state_metrics import bucket_metrics, distribution, validate_minutes


def bars_from_closes(closes, opening=100):
    result = []
    previous = opening
    for close in closes:
        result.append(dict(open=previous, high=max(previous, close), low=min(previous, close), close=close, volume=10))
        previous = close
    return result


class MarketStateTests(unittest.TestCase):
    def test_monotone_path_efficiency_and_no_reversals(self):
        r = bucket_metrics(bars_from_closes(list(range(101, 116))))
        self.assertEqual(r['directional_efficiency'], 1)
        self.assertEqual(r['net_points'], 15)
        self.assertEqual(r['five_minute_eligible_pairs'], 2)
        self.assertEqual(r['five_minute_reversal_fraction'], 0)
        self.assertEqual(r['volume_per_minute'], 10)

    def test_round_trip_and_sign_changes(self):
        r = bucket_metrics(bars_from_closes([101]*5 + [100]*5 + [101]*5 + [100]*5))
        self.assertEqual(r['directional_efficiency'], 0)
        self.assertEqual(r['close_path_points'], 4)
        self.assertEqual(r['five_minute_reversals'], 3)
        self.assertEqual(r['five_minute_reversal_fraction'], 1)

    def test_flat_path_is_undefined_not_directional(self):
        r = bucket_metrics(bars_from_closes([100]*10))
        self.assertIsNone(r['directional_efficiency'])
        self.assertIsNone(r['five_minute_reversal_fraction'])
        self.assertEqual(r['five_minute_zero_excluded_pairs'], 1)
        self.assertEqual(r['rms_log_move_bps'], 0)

    def test_zero_block_does_not_connect_nonadjacent_moves(self):
        r = bucket_metrics(bars_from_closes([101]*5 + [101]*5 + [100]*5))
        self.assertEqual(r['five_minute_eligible_pairs'], 0)
        self.assertEqual(r['five_minute_reversals'], 0)
        self.assertEqual(r['five_minute_zero_excluded_pairs'], 2)

    def test_first_open_anchor_and_rms_not_centered_sd(self):
        r = bucket_metrics(bars_from_closes([101]*5))
        self.assertAlmostEqual(r['rms_log_move_bps'], 10000*math.log(1.01)/math.sqrt(5))
        self.assertEqual(r['directional_efficiency'], 1)

    def test_new_bucket_resets_at_own_open(self):
        # A gap from a previous bucket is not a movement of this bucket.
        first = bucket_metrics(bars_from_closes([100]*5, opening=99))
        second = bucket_metrics(bars_from_closes([200]*5, opening=200))
        self.assertEqual(first['net_points'], 1)
        self.assertEqual(second['net_points'], 0)
        self.assertEqual(second['rms_log_move_bps'], 0)
        self.assertEqual(second['five_minute_total_pairs'], 0)

    def test_quantiles_and_missing_are_session_weighted(self):
        r = distribution([1, 2, 3, 4, None])
        self.assertEqual((r['median'], r['q1'], r['q3']), (2.5, 1.75, 3.25))
        self.assertEqual((r['count'], r['missing']), (4, 1))
        self.assertIsNone(distribution([None])['median'])

    def test_minute_keys_sorted_numerically_and_gaps_rejected(self):
        m = {str(k): b for k, b in zip(range(998, 1003), bars_from_closes([101]*5))}
        ordered = validate_minutes(m, 998, 1003)
        self.assertEqual(ordered[0]['open'], 100)
        del m['1000']
        with self.assertRaises(ValueError):
            validate_minutes(m, 998, 1003)

    def test_bad_price_volume_range_and_incomplete_block_rejected(self):
        for field, value in [('open', float('nan')), ('close', 100.1), ('volume', 0), ('volume', 1.5), ('high', 99)]:
            m = {'570': bars_from_closes([101])[0]}
            m['570'][field] = value
            with self.assertRaises(ValueError):
                validate_minutes(m, 570, 571)
        with self.assertRaises(ValueError):
            bucket_metrics(bars_from_closes([101]*6))


if __name__ == '__main__':
    unittest.main()
