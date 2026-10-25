import copy
import unittest
from research.state_response_metrics import features, response, extract_event, spearman, ranks, event_summary, day_summary


def bars(start=100, step=.25, count=30):
    return [dict(open=start+i*step, close=start+(i+1)*step,
                 low=min(start+i*step,start+(i+1)*step),
                 high=max(start+i*step,start+(i+1)*step), volume=10)
            for i in range(count)]


def refs(past=2, future=3):
    return [dict(date=f'2026-10-{d:02d}', clock=600, past_rms=past, future_rms=future) for d in range(1, 6)]


def session():
    return {str(i): b for i, b in zip(range(570, 650), bars(count=80))}


class StateResponseTests(unittest.TestCase):
    def test_feature_only_sees_prefix_and_rejects_current_minute(self):
        s = session()
        with self.assertRaises(ValueError):
            features(s, 600, refs(), '2026-10-06')
        r = features({k:v for k,v in s.items() if int(k)<600}, 600, refs(), '2026-10-06')
        self.assertEqual(r['signed_efficiency'], 1)
        self.assertEqual(r['feature_last_minute'], 599)

    def test_future_changes_cannot_change_features_or_forecast(self):
        a = session(); b = copy.deepcopy(a)
        for m in range(601, 631):
            b[str(m)] = bars(start=500, step=-.5)[m-601]
        fa, ra = extract_event(a, 600, refs(), '2026-10-06')
        fb, rb = extract_event(b, 600, refs(), '2026-10-06')
        self.assertEqual(fa, fb)
        self.assertNotEqual(ra['future_log_move_bps'], rb['future_log_move_bps'])

    def test_gap_and_post_horizon_do_not_change_event(self):
        a = session(); b = copy.deepcopy(a)
        b['600'] = bars(start=9999)[0]
        for m in range(631, 650):
            b[str(m)] = bars(start=9999)[0]
        self.assertEqual(extract_event(a, 600, refs(), '2026-10-06'), extract_event(b, 600, refs(), '2026-10-06'))

    def test_response_starts_at_next_minute_open_not_feature_close(self):
        s = session()
        for m in range(601, 631):
            s[str(m)] = bars(start=500, step=0)[0]
        f, r = extract_event(s, 600, refs(), '2026-10-06')
        self.assertEqual(r['future_net_points'], 0)
        self.assertEqual(r['future_log_move_bps'], 0)
        self.assertEqual(r['continuation'], 'neutral')

    def test_reference_rejects_same_day_duplicate_or_wrong_clock(self):
        prefix = {str(i):b for i,b in zip(range(570,600),bars())}
        same = refs(); same[0]['date'] = '2026-10-06'
        duplicate = refs(); duplicate[0]['date'] = duplicate[1]['date']
        wrong = refs(); wrong[0]['clock'] = 660
        for altered in (same, duplicate, wrong):
            with self.assertRaises(ValueError):
                features(prefix, 600, altered, '2026-10-06')

    def test_fixed_forecast_and_control_use_five_prior_days(self):
        prefix = {str(i):b for i,b in zip(range(570,600),bars())}
        r = refs(); r[-1].update(past_rms=1000, future_rms=2000)
        f = features(prefix, 600, r, '2026-10-06')
        self.assertEqual(f['reference_past_rms'], 2)
        self.assertEqual(f['control_rms'], 3)
        self.assertAlmostEqual(f['forecast_rms'], 3*f['past_rms']/2)

    def test_zero_reference_and_flat_path_undefined(self):
        prefix = {str(i):b for i,b in zip(range(570,600),bars(step=0))}
        f = features(prefix, 600, refs(past=0, future=0), '2026-10-06')
        self.assertIsNone(f['signed_efficiency'])
        self.assertIsNone(f['relative_past_rms'])
        self.assertIsNone(f['forecast_rms'])
        r = response(bars(), f)
        self.assertIsNone(r['relative_future_rms'])
        self.assertEqual(r['continuation'], 'undefined_past_direction')

    def test_rank_ties_and_monotonic_correlations(self):
        self.assertEqual(ranks([3,1,1,2]), [4,1.5,1.5,3])
        self.assertEqual(spearman([1,2,2,4],[10,20,20,40])['rho'], 1)
        self.assertEqual(spearman([1,2,3],[-1,-2,-3])['rho'], -1)

    def test_undefined_correlation_not_zero_imputed(self):
        self.assertIsNone(spearman([1,1,1],[1,2,3])['rho'])
        self.assertEqual(spearman([1,None,3],[1,2,3])['pairs'], 2)
        with self.assertRaises(ValueError):
            spearman([1,2,float('nan')],[1,2,3])

    def test_neutral_in_continuation_denominator_and_error_pairing(self):
        f, r = extract_event(session(), 600, refs(), '2026-10-06')
        first = dict(f, **r); second = dict(first, continuation='neutral')
        third = dict(first, continuation='undefined_past_direction')
        summary = event_summary([first,second,third])
        self.assertEqual(summary['continuation_eligible'], 2)
        self.assertEqual(summary['continuation_fraction'], .5)
        self.assertAlmostEqual(summary['mae_improvement'], summary['control_mae']-summary['forecast_mae'])

    def test_day_equal_weight_not_event_count(self):
        def d(rho, error, pairs):
            return dict(h1=dict(rho=rho), h2=dict(rho=rho), continuation_fraction=.5,
                        mae_improvement=error, forecast_mae=1, control_mae=1+error, forecast_pairs=pairs)
        summary = day_summary([d(.1,1,6),d(.5,3,2)])
        self.assertEqual(summary['mean_mae_improvement'], 2)
        self.assertAlmostEqual(summary['h1_daily_rho']['median'], .3)


if __name__ == '__main__':
    unittest.main()
