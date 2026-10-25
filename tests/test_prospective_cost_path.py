"""Synthetic fixtures only; no real market data or native calls."""
import copy
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from research.prospective_cost_path import assess_cost_path

ET = ZoneInfo('America/New_York')


def stamp(day, hour=10, minute=0):
    value = datetime.fromisoformat(day).replace(hour=hour, minute=minute, tzinfo=ET)
    # Calendar fixture, integral seconds converted before multiplying.
    return int(value.astimezone(timezone.utc).timestamp()) * 1000000000


def trade(day, entry=100, exit_=110, minute=0, side='Long'):
    clock = stamp(day, minute=minute)
    return dict(date=day, side=side, qty=1, entry_name='L' if side == 'Long' else 'S',
                exit_name='TimeExit', signal_utc_ns=clock - 1000000000,
                entry_utc_ns=clock + 100, exit_utc_ns=clock + 1000000100,
                entry_price=entry, exit_price=exit_, gross_pnl=(exit_ - entry)*20*(1 if side == 'Long' else -1))


def last(day, trades):
    rows = [(stamp(day, hour=9, minute=30), 100)]
    for t in trades:
        rows.extend([(t['entry_utc_ns'] - 100, t['entry_price']),
                     (t['entry_utc_ns'], t['entry_price']),
                     (t['entry_utc_ns'] + 100, min(t['entry_price'], t['exit_price']) - 1),
                     (t['exit_utc_ns'], t['exit_price']),
                     (t['exit_utc_ns'] + 100, t['exit_price'])])
    rows.append((stamp(day, hour=16), 100))
    rows.sort()
    return dict(timestamps_ns=[r[0] for r in rows], prices=[r[1] for r in rows])


def fixture(trades, dates=None):
    dates = dates or sorted({t['date'] for t in trades})
    return trades, dates, {d: last(d, [t for t in trades if t['date'] == d]) for d in dates}


class ProspectiveCostPathTests(unittest.TestCase):
    def test_fixed_fees_stress_and_best_positive_day(self):
        rows = [trade('2026-10-26'), trade('2026-10-27')]
        args = fixture(rows, ['2026-10-26', '2026-10-27', '2026-10-28'])
        before = copy.deepcopy(args)
        r = assess_cost_path(*args)
        self.assertEqual(args, before)
        self.assertEqual(r['fee_cases']['5']['net'], 390)
        high = r['fee_cases']['10']
        self.assertEqual(high['net'], 380)
        self.assertEqual(high['additional_tick_stress']['2']['net'], 340)
        self.assertEqual(high['additional_tick_stress']['4']['net'], 300)
        self.assertEqual(high['best_positive_day_removed'], 190)
        self.assertEqual(high['daily_net']['2026-10-28'], 0)
        self.assertEqual(high['aggregate_path']['net'], high['net'])
        self.assertTrue(r['cost_gate_passed']); self.assertTrue(r['concentration_gate_passed'])
        self.assertFalse(r['strategy_validated']); self.assertFalse(r['live_trading_authorized'])
        self.assertEqual(r['native_submissions'], 0)

    def test_day_removal_is_not_best_trade_removal(self):
        rows = [trade('2026-10-26'), trade('2026-10-26', minute=2), trade('2026-10-27', exit_=95)]
        r = assess_cost_path(*fixture(rows))
        self.assertEqual(r['fee_cases']['10']['best_positive_day_removed'], -110)
        self.assertFalse(r['concentration_gate_passed'])

    def test_negative_days_are_not_removed(self):
        rows = [trade('2026-10-26', exit_=99), trade('2026-10-27', exit_=98)]
        high = assess_cost_path(*fixture(rows))['fee_cases']['10']
        self.assertEqual(high['best_positive_day_removed'], high['net'])
        self.assertEqual(high['descriptive']['maximum_loss_streak'], 2)
        self.assertEqual(high['descriptive']['profit_factor'], 0)

    def test_zero_trades_and_days_are_explicit(self):
        args = fixture([], ['2026-10-26', '2026-10-27'])
        r = assess_cost_path(*args)
        self.assertEqual(r['decision'], 'not_performance_evaluable')
        self.assertFalse(r['cost_gate_passed']); self.assertFalse(r['concentration_gate_passed'])
        self.assertEqual(r['fee_cases']['10']['aggregate_path']['holding_path_drawdown_upper'], 0)
        self.assertIsNone(r['fee_cases']['10']['descriptive']['profit_factor'])

    def test_short_direction_and_path_reconcile(self):
        row = trade('2026-10-26', exit_=90, side='Short')
        r = assess_cost_path(*fixture([row]))
        self.assertEqual(r['fee_cases']['10']['net'], 190)
        self.assertEqual(r['fee_cases']['10']['aggregate_path']['final_equity'], 150190)

    def test_loss_halt_is_entry_gate_not_hard_cap(self):
        rows = [trade('2026-10-26', exit_=88, minute=m) for m in (0, 2, 4, 6)]
        r = assess_cost_path(*fixture(rows))
        self.assertEqual(r['high_fee_realized_overshoot_beyond900']['2026-10-26'], 100)
        self.assertEqual(r['fee_cases']['10']['closed_trade_drawdown'], 1000)
        bad = [trade('2026-10-26', exit_=50), trade('2026-10-26', minute=2)]
        with self.assertRaisesRegex(ValueError, 'realized -900'):
            assess_cost_path(*fixture(bad))

    def test_more_than_four_entries_rejected(self):
        rows = [trade('2026-10-26', minute=m) for m in (0, 2, 4, 6, 8)]
        with self.assertRaisesRegex(ValueError, 'four entries'):
            assess_cost_path(*fixture(rows))

    def test_equal_timestamp_cross_trade_reports_solver_limit(self):
        a = trade('2026-10-26')
        b = trade('2026-10-26', entry=110, exit_=120, minute=2)
        b.update(signal_utc_ns=a['exit_utc_ns'], entry_utc_ns=a['exit_utc_ns'])
        r = assess_cost_path(*fixture([a, b]))
        self.assertFalse(r['path_evidence_complete'])
        self.assertEqual(r['decision'], 'pending_path_evidence')
        self.assertEqual(r['fee_cases']['10']['aggregate_path']['status'], 'unresolved_equal_timestamp_cross_trade')
        self.assertIsNone(r['fee_cases']['10']['maximum_intraday_loss_from_day_start_upper'])

    def test_fullprecision_does_not_resolve_same_timestamp_last_order(self):
        row = trade('2026-10-26', exit_=100)
        data = last('2026-10-26', [row])
        at = data['timestamps_ns'].index(row['entry_utc_ns'])
        data['timestamps_ns'].insert(at + 1, row['entry_utc_ns'])
        data['prices'].insert(at + 1, 120)
        r = assess_cost_path([row], ['2026-10-26'], {'2026-10-26': data})
        path = r['fee_cases']['10']['aggregate_path']
        self.assertGreater(path['holding_path_drawdown_upper'], path['holding_path_drawdown_lower'])

    def test_dst_dates_and_100ns_survive(self):
        rows = [trade('2026-10-30'), trade('2026-11-02')]
        r = assess_cost_path(*fixture(rows))
        self.assertEqual(r['realized_entry_gate_checks'][0]['entry_utc_ns'], rows[0]['entry_utc_ns'])
        self.assertEqual((stamp('2026-11-02') - stamp('2026-10-30')) // 1000000000, 3*86400 + 3600)

    def test_malformed_trade_fields(self):
        base = trade('2026-10-26')
        for field, value in [('qty', True), ('qty', 2), ('side', 'Other'), ('entry_price', 100.1),
                             ('gross_pnl', float('nan')), ('gross_pnl', 1), ('exit_name', ''),
                             ('entry_utc_ns', float(base['entry_utc_ns'])),
                             ('entry_utc_ns', base['entry_utc_ns'] + 1), ('entry_name', 'S')]:
            row = dict(base); row[field] = value
            # Keep valid Last fixture separate so trade validation is the subject.
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                assess_cost_path([row], ['2026-10-26'], {'2026-10-26': last('2026-10-26', [base])})

    def test_no_overnight_overlap_or_duplicate(self):
        row = trade('2026-10-26'); wrong = dict(row, exit_utc_ns=stamp('2026-10-27'))
        with self.assertRaises(ValueError):
            assess_cost_path([wrong], ['2026-10-26'], {'2026-10-26': last('2026-10-26', [row])})
        for rows in ([row, row], [trade('2026-10-26', minute=2), row]):
            with self.assertRaises(ValueError):
                assess_cost_path(*fixture(rows))

    def test_subsecond_after_session_close_is_rejected(self):
        row = trade('2026-10-26')
        row['exit_utc_ns'] = stamp('2026-10-26', hour=16) + 100
        with self.assertRaisesRegex(ValueError, 'same-day ET RTH'):
            assess_cost_path(*fixture([row]))

    def test_missing_extra_bad_or_unsorted_last_rejected(self):
        row = trade('2026-10-26'); args = fixture([row])
        for data in ({}, {'2026-10-26': args[2]['2026-10-26'], '2026-10-27': args[2]['2026-10-26']}):
            with self.assertRaises(ValueError):
                assess_cost_path([row], ['2026-10-26'], data)
        for mutate in ('unsorted', 'bad_price', 'float_clock', 'missing_context', 'empty'):
            data = copy.deepcopy(args[2]); d = data['2026-10-26']
            if mutate == 'unsorted': d['timestamps_ns'].reverse()
            if mutate == 'bad_price': d['prices'][0] = float('inf')
            if mutate == 'float_clock': d['timestamps_ns'][0] = float(d['timestamps_ns'][0])
            if mutate == 'missing_context':
                d['timestamps_ns'] = [row['entry_utc_ns'], row['exit_utc_ns']]
                d['prices'] = [100, 110]
            if mutate == 'empty': d.update(timestamps_ns=[], prices=[])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                assess_cost_path([row], ['2026-10-26'], data)


if __name__ == '__main__':
    unittest.main()
