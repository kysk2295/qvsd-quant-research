"""Synthetic fixtures only. No native output or market-data files are read."""
from datetime import datetime, timezone
import unittest
from zoneinfo import ZoneInfo

from research.prospective_clock import local_stamp_ns, reconcile_clocks


DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30',
         '2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06']


def net_ticks(stamp):
    wall = datetime.fromisoformat(stamp[:19])
    fraction = int(stamp[20:27])
    return ((wall.toordinal() - 1) * 86400 + wall.hour * 3600 + wall.minute * 60 + wall.second) * 10_000_000 + fraction


def native_stamp(day, clock, zone='UTC'):
    wall = datetime.fromisoformat(day + 'T' + clock[:8]).replace(tzinfo=ZoneInfo('America/New_York'))
    converted = wall.astimezone(ZoneInfo(zone))
    fraction = clock[9:] if len(clock) > 8 else '0000000'
    return converted.strftime('%Y-%m-%dT%H:%M:%S') + '.' + fraction


def clock_record(kind, entry, exit_=None):
    values = [kind, entry, str(net_ticks(entry))]
    if exit_ is not None:
        values += [exit_, str(net_ticks(exit_))]
    return '|'.join(values)


def synthetic_fixture(specs=None, zone='UTC'):
    """One default long trade; specs=[] covers all ten zero-trade dates."""
    if specs is None:
        specs = [dict(day=0, side='L')]
    output, trades, cumulative = [], [], []
    for day_index, day in enumerate(DATES):
        day_specs = [item for item in specs if item['day'] == day_index]
        for item in day_specs:
            side = item.get('side', 'L')
            signal_clock = item.get('signal', '10:00:00')
            entry_clock = item.get('entry', '10:00:00.1234567')
            exit_clock = item.get('exit', '10:01:00.7654321')
            entry = native_stamp(day, entry_clock, zone)
            exit_ = native_stamp(day, exit_clock, zone)
            submit = native_stamp(day, signal_clock, zone)
            entry_primary = native_stamp(day, item.get('entry_primary', '10:01:00'), zone)
            exit_primary = native_stamp(day, item.get('exit_primary', '10:02:00'), zone)
            entry_price, exit_price = item.get('entry_price', 20000), item.get('exit_price', 20000.5)
            exit_name = item.get('exit_name', 'TimeExit')
            output.append(f'SIGNAL {day}T{signal_clock} side={side} close=20000 mean=20001 lower=19999 upper=20003')
            output.append(clock_record('CLOCK_SUBMIT', submit) + f'|{side}|20000')
            output.append(clock_record('CLOCK_EXEC', entry, entry) + f'|{entry_primary}|{side}|{entry_price}|1|Historical')
            output.append(clock_record('CLOCK_EXEC', exit_, exit_) + f'|{exit_primary}|{exit_name}|{exit_price}|1|Historical')
            cumulative.append(clock_record('CLOCK_TRADE', entry, exit_))
            trades.append(dict(n=len(trades) + 1, side='Long' if side == 'L' else 'Short', qty=1,
                               entryName=side, exitName=exit_name, entryTime=entry[:19], exitTime=exit_[:19],
                               entryPrice=entry_price, exitPrice=exit_price,
                               pnl=(exit_price - entry_price) * (20 if side == 'L' else -20)))
        output.extend(cumulative)
        output.append(f'AUDIT {day.replace("-", "")} bars=390 gap=False entries={len(day_specs)}')
    return output, trades


class ProspectiveClockTests(unittest.TestCase):
    def check(self, output, trades, zone='UTC', dates=None):
        return reconcile_clocks(output, trades, DATES if dates is None else dates, zone)

    def test_exact_100ns_normalization_and_output_indices(self):
        output, trades = synthetic_fixture()
        result = self.check(output, trades)
        row = result['trades'][0]
        self.assertTrue(result['passed'])
        self.assertFalse(result['strategy_validated'])
        self.assertEqual(row['entry_utc_ns'] % 1_000_000_000, 123456700)
        self.assertEqual(row['exit_utc_ns'] % 1_000_000_000, 765432100)
        self.assertEqual([row[k] for k in ('signal_output_index', 'submit_output_index',
                                         'entry_output_index', 'exit_output_index')], [0, 1, 2, 3])
        self.assertEqual(row['entry_primary_local'], '2026-10-26T14:01:00.0000000')
        self.assertEqual(result['audits'][-1]['cumulative_trades'], 1)
        self.assertEqual(result['equal_timestamp_last_ordering'], 'unknown')
        self.assertEqual(row['gross_pnl'], 10)

    def test_windows_iana_mapping_and_dst_offset_change(self):
        self.assertEqual(local_stamp_ns('2026-10-30T10:00:00.0000001', 'Eastern Standard Time'),
                         local_stamp_ns('2026-10-30T14:00:00.0000001', 'UTC'))
        self.assertEqual(local_stamp_ns('2026-11-02T10:00:00.0000001', 'America/New_York'),
                         local_stamp_ns('2026-11-02T15:00:00.0000001', 'UTC'))
        self.assertEqual(local_stamp_ns('2026-10-30T23:00:00.0000001', 'Korea Standard Time'),
                         local_stamp_ns('2026-10-30T14:00:00.0000001Z', 'UTC'))

    def test_ambiguous_nonexistent_unknown_and_wrong_offset_rejected(self):
        for stamp, zone in [('2026-11-01T01:30:00.0000000', 'Eastern Standard Time'),
                            ('2026-11-01T01:30:00.0000000-04:00', 'Eastern Standard Time'),
                            ('2026-03-08T02:30:00.0000000', 'America/New_York'),
                            ('2026-10-26T10:00:00.0000000Z', 'America/New_York'),
                            ('2026-10-26T10:00:00.12345678', 'UTC'),
                            ('2026-10-26T10:00:00', ''), ('2026-10-26T10:00:00', 'Unknown')]:
            with self.subTest(stamp=stamp, zone=zone), self.assertRaises(ValueError):
                local_stamp_ns(stamp, zone)

    def test_whole_seconds_and_seven_digits_use_integer_arithmetic(self):
        delta = datetime(2026, 10, 26, 8, tzinfo=timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
        expected = (delta.days * 86400 + delta.seconds) * 1_000_000_000
        self.assertEqual(local_stamp_ns('2026-10-26T08:00:00', 'UTC'), expected)
        self.assertEqual(local_stamp_ns('2026-10-26T08:00:00.0000001', 'UTC'), expected + 100)

    def test_zero_trade_dates_and_short_across_dst(self):
        output, trades = synthetic_fixture([])
        result = self.check(output, trades)
        self.assertEqual(result['trades'], [])
        self.assertEqual(len(result['audits']), 10)
        output, trades = synthetic_fixture([dict(day=5, side='S')], 'America/New_York')
        result = self.check(output, trades, 'Eastern Standard Time')
        self.assertEqual(result['trades'][0]['side'], 'Short')
        self.assertEqual(result['trades'][0]['gross_pnl'], -10)

    def test_ticks_and_fractional_iso_mismatch_rejected(self):
        for index in (1, 2, 4):
            output, trades = synthetic_fixture()
            fields = output[index].split('|'); fields[2] = str(int(fields[2]) + 1)
            output[index] = '|'.join(fields)
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.check(output, trades)

    def test_callback_time_quantity_and_historical_state_required(self):
        for field, value in [(4, '1'), (8, '2'), (9, 'Realtime')]:
            output, trades = synthetic_fixture()
            fields = output[2].split('|'); fields[field] = value; output[2] = '|'.join(fields)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(output, trades)

    def test_signal_submit_time_side_and_close_must_match(self):
        for edit in (lambda s: s.replace('side=L', 'side=S'),
                     lambda s: s.replace('10:00:00', '10:01:00'),
                     lambda s: s.replace('close=20000', 'close=20001')):
            output, trades = synthetic_fixture(); output[0] = edit(output[0])
            with self.assertRaises(ValueError):
                self.check(output, trades)

    def test_cumulative_snapshot_prefix_missing_changed_or_duplicated_rejected(self):
        output, trades = synthetic_fixture()
        snapshot_indices = [i for i, line in enumerate(output) if line.startswith('CLOCK_TRADE|')]
        for variant in ('missing', 'changed', 'duplicate'):
            changed = list(output); target = snapshot_indices[1]
            if variant == 'missing':
                del changed[target]
            elif variant == 'duplicate':
                changed.insert(target, changed[target])
            else:
                fields = changed[target].split('|')
                fields[1] = fields[1].replace('1234567', '1234568')
                fields[2] = str(int(fields[2]) + 1)
                changed[target] = '|'.join(fields)
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.check(changed, trades)

    def test_cumulative_growth_and_trade_order_are_not_set_deduplicated(self):
        output, trades = synthetic_fixture([dict(day=0, side='L'), dict(day=1, side='S')])
        result = self.check(output, trades)
        self.assertEqual([a['cumulative_trades'] for a in result['audits']], [1] + [2] * 9)
        with self.assertRaises(ValueError):
            self.check(output, list(reversed(trades)))

    def test_native_whole_second_serializer_prices_names_quantity_and_pnl(self):
        edits = [dict(entryTime='2026-10-26T14:00:01'), dict(exitTime='2026-10-26T14:01:00.7654321'),
                 dict(entryPrice=20000.25), dict(exitName='OtherExit'), dict(qty=True),
                 dict(side='Short'), dict(pnl=11), dict(pnl=float('nan'))]
        for edit in edits:
            output, trades = synthetic_fixture(); trades[0].update(edit)
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                self.check(output, trades)

    def test_incomplete_unfilled_open_position_and_extra_execution_fail_closed(self):
        output, trades = synthetic_fixture()
        for indices in ([1], [2], [3]):
            changed = [line for i, line in enumerate(output) if i not in indices]
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                self.check(changed, trades)
        changed = output[:3] + [output[2]] + output[3:]
        with self.assertRaises(ValueError):
            self.check(changed, trades)

    def test_wrong_audit_date_coverage_gap_and_daily_count_rejected(self):
        for edit in (lambda s: s.replace('bars=390', 'bars=389'),
                     lambda s: s.replace('gap=False', 'gap=True'),
                     lambda s: s.replace('entries=1', 'entries=0'),
                     lambda s: s.replace('20261026', '20261027')):
            output, trades = synthetic_fixture(); output[5] = edit(output[5])
            with self.assertRaises(ValueError):
                self.check(output, trades)
        output, trades = synthetic_fixture()
        with self.assertRaises(ValueError):
            self.check(output[:-1], trades)

    def test_entry_window_and_four_submission_cap(self):
        for signal in ('09:50:00', '15:26:00'):
            output, trades = synthetic_fixture([dict(day=0, signal=signal)])
            with self.subTest(signal=signal), self.assertRaises(ValueError):
                self.check(output, trades)
        specs = [dict(day=0, signal=f'{10+i}:00:00', entry=f'{10+i}:00:00.1234567',
                      exit=f'{10+i}:01:00.7654321') for i in range(5)]
        output, trades = synthetic_fixture(specs)
        with self.assertRaises(ValueError):
            self.check(output, trades)

    def test_no_invented_fill_delay_or_exit_cutoff(self):
        output, trades = synthetic_fixture([dict(day=0, signal='15:25:00',
            entry='15:27:00.0000001', exit='15:56:00.0000001')])
        self.assertTrue(self.check(output, trades)['passed'])

    def test_prior_fractional_exit_before_next_signal_output_can_follow_its_bar_label(self):
        output, trades = synthetic_fixture([
            dict(day=0, exit='10:01:00.0000001'),
            dict(day=0, side='S', signal='10:01:00', entry='10:01:00.0000002',
                 exit='10:02:00.0000003', entry_primary='10:01:00'),
        ])
        first, second = self.check(output, trades)['trades']
        self.assertLess(second['signal_utc_ns'], first['exit_utc_ns'])
        self.assertLess(first['exit_utc_ns'], second['entry_utc_ns'])
        self.assertLess(first['exit_output_index'], second['signal_output_index'])
        self.assertLess(second['signal_output_index'], second['entry_output_index'])

    def test_entry_before_own_signal_bar_label_and_overnight_exit_rejected(self):
        output, trades = synthetic_fixture([dict(day=0, entry='09:59:59.0000001')])
        with self.assertRaises(ValueError):
            self.check(output, trades)
        output, trades = synthetic_fixture()
        fields = output[3].split('|')
        for index in (1, 3):
            fields[index] = fields[index].replace('2026-10-26', '2026-10-27')
            fields[index + 1] = str(net_ticks(fields[index]))
        output[3] = '|'.join(fields)
        with self.assertRaises(ValueError):
            self.check(output, trades)

    def test_input_shapes_bad_dates_order_errors_and_unrecognized_clocks(self):
        output, trades = synthetic_fixture()
        for altered_output, altered_trades, dates in [(None, trades, DATES), (output, None, DATES),
                (output, trades, DATES[:-1]), (output, trades, list(reversed(DATES))),
                (output + ['ORDER_ERROR Synthetic failure'], trades, DATES),
                (output + ['CLOCK_UNKNOWN|anything'], trades, DATES)]:
            with self.assertRaises(ValueError):
                self.check(altered_output, altered_trades, dates=dates)


if __name__ == '__main__':
    unittest.main()
