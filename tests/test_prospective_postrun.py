"""Manufactured ten-session fixtures. No saved market outcomes are loaded."""
import copy
import json
import math
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from research.prospective_postrun import (assess_postrun, raw_minute_closes,
    reconcile_bars_and_entries, observed_last_fill_evidence, MINUTE)
from tests.test_prospective_execution_contract import fixture as native_fixture


def ns(dt):
    delta = dt.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 10**9 + delta.microseconds * 1000


def clock_stamp(value):
    seconds, fraction = divmod(value, 10**9)
    dt = datetime.fromtimestamp(seconds, timezone.utc).astimezone(ZoneInfo('Asia/Seoul')).replace(tzinfo=None)
    delta = dt - datetime(1, 1, 1)
    ticks = (delta.days * 86400 + delta.seconds) * 10**7 + fraction // 100
    return dt.isoformat() + '.' + str(fraction // 100).zfill(7), ticks


def fixture(with_trades=False, exit_on_cross_bar=False):
    # Frozen metadata only; no files containing market outcomes.
    plan = json.loads((Path(__file__).resolve().parents[1] / 'research/bollinger-prospective-plan.json').read_text())
    _, document = native_fixture()
    document['output'], document['trades'] = [], []
    raw, normalized, snapshots = {}, [], []
    for day in plan['evaluation_dates']:
        opening = datetime.fromisoformat(day + 'T09:30:00').replace(tzinfo=ZoneInfo('America/New_York'))
        start = ns(opening)
        closes = [100.0] * 390
        if with_trades:
            closes[19:22] = [90.0, 90.0, 100.0]
            if exit_on_cross_bar:
                closes[22] = 110.0
        ticks = [(start + m * MINUTE + 59 * 10**9, p) for m, p in enumerate(closes)]
        window, prior, trade = [], None, None
        for m, close in enumerate(closes):
            label = (opening.replace(tzinfo=None) + timedelta(minutes=m+1)).isoformat()
            end = start + (m+1) * MINUTE
            window = (window + [close])[-20:]
            direction = 0
            mean = lower = upper = 0.0
            if len(window) == 20:
                mean = math.fsum(window) / 20
                deviation = 2 * math.sqrt(math.fsum((x-mean)**2 for x in window) / 20)
                lower, upper = mean - deviation, mean + deviation
                if prior:
                    direction = 1 if prior[0] <= prior[1] and close > lower else -1 if prior[0] >= prior[2] and close < upper else 0
                prior = close, lower, upper
            document['output'].append(f'BAR {label} close={close} mean={mean} lower={lower} upper={upper} side={direction}')
            if with_trades and m == 21:
                signal_index = len(document['output'])
                document['output'].append(f'SIGNAL {label} side=L close={close} mean={mean} lower={lower} upper={upper}')
                ss, st = clock_stamp(end)
                document['output'].append(f'CLOCK_SUBMIT|{ss}|{st}|L|{close}')
                en = end + 123456700
                es, et = clock_stamp(en)
                entry_index = len(document['output'])
                document['output'].append(f'CLOCK_EXEC|{es}|{et}|{es}|{et}|{ss}|L|100|1|Historical')
                ticks.append((en, 100.0))
                trade = dict(date=day, side='Long', qty=1, entry_name='L', exit_name='TimeExit',
                    signal_utc_ns=end, entry_utc_ns=en, entry_price=100.0,
                    signal_output_index=signal_index, submit_output_index=signal_index+1,
                    entry_output_index=entry_index)
            if with_trades and m == (23 if exit_on_cross_bar else 22):
                ex = end + 234567800
                xs, xt = clock_stamp(ex)
                primary, _ = clock_stamp(end)
                trade['exit_output_index'] = len(document['output'])
                document['output'].append(f'CLOCK_EXEC|{xs}|{xt}|{xs}|{xt}|{primary}|TimeExit|125|1|Historical')
                ticks.append((ex, 125.0))
                trade.update(exit_utc_ns=ex, exit_price=125.0, gross_pnl=500.0)
                normalized.append(trade)
                es, et = clock_stamp(trade['entry_utc_ns'])
                snapshots.append(f'CLOCK_TRADE|{es}|{et}|{xs}|{xt}')
                document['trades'].append(dict(n=len(normalized), side='Long', qty=1,
                    entryName='L', exitName='TimeExit', entryPrice=100.0, exitPrice=125.0,
                    entryTime=es[:19], exitTime=xs[:19], pnl=500.0, pnlPoints=25.0, bars=1))
        document['output'].extend(snapshots)
        document['output'].append(f'AUDIT {day.replace("-", "")} bars=390 gap=False entries={int(with_trades)}')
        document['output'].append(f'COUNTS {day.replace("-", "")} entry_submitted={int(with_trades)} exit_submitted={int(with_trades)}')
        ticks.sort(key=lambda x: x[0])
        raw[day] = dict(timestamps_ns=[x[0] for x in ticks], prices=[x[1] for x in ticks])
    document['summary']['trades'] = len(document['trades'])
    binding = dict(job_id='b1', expected_instance='instance1', observed_instance='instance1', native_time_zone='Korea Standard Time')
    return plan, document, raw, binding, normalized


class PostrunTests(unittest.TestCase):
    def test_zero_trade_full_ten_sessions_never_becomes_validated(self):
        plan, doc, raw, binding, _ = fixture()
        result = assess_postrun(plan, doc, raw, binding)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['entries']['verified_bars'], 3900)
        self.assertEqual(result['decision'], 'condition_absent_not_performance_evaluable')
        self.assertFalse(result['strategy_validated'])
        self.assertFalse(result['performance_evaluated'])

    def test_complete_synthetic_profitable_pipeline_keeps_unproven_evidence_pending(self):
        plan, doc, raw, binding, _ = fixture(True)
        result = assess_postrun(plan, doc, raw, binding)
        self.assertEqual(result['errors'], [])
        self.assertTrue(result['component_reconciliation_passed'])
        self.assertTrue(result['costs']['cost_gate_passed'])
        self.assertTrue(result['costs']['concentration_gate_passed'])
        self.assertEqual(result['entries']['verified_entries'], 10)
        self.assertEqual(len(result['clock']['trades']), 10)  # 55 cumulative rows are not 55 trades.
        self.assertFalse(result['postrun_parity_complete'])
        self.assertFalse(result['strategy_validated'])
        self.assertFalse(result['entries']['exit_order_causality_verified'])
        self.assertTrue(result['pending_evidence'])

    def test_raw_minute_boundary_ties_and_dst_are_preserved(self):
        plan, doc, raw, _, _ = fixture()
        dates = plan['evaluation_dates']
        first, second_week = dates[0], dates[5]
        original = raw_minute_closes(raw, dates)
        start = original[first + 'T09:31:00']['utc_ns'] - MINUTE
        stream = raw[first]
        stream['timestamps_ns'][1:1] = [start + MINUTE, start + MINUTE]
        stream['prices'][1:1] = [101.0, 102.0]
        fresh = raw_minute_closes(raw, dates)
        self.assertEqual(fresh[first + 'T09:31:00']['close'], 100)
        self.assertEqual(fresh[first + 'T09:32:00']['close'], 100)
        self.assertEqual((fresh[first + 'T09:31:00']['utc_ns'] // 10**9) % 86400, 13*3600+31*60)
        self.assertEqual((fresh[second_week + 'T09:31:00']['utc_ns'] // 10**9) % 86400, 14*3600+31*60)
        # The last event at a tied timestamp must win, not a price sort or dedupe.
        stream['timestamps_ns'].insert(1, start + 59*10**9)
        stream['prices'].insert(1, 99.75)
        self.assertEqual(raw_minute_closes(raw, dates)[first + 'T09:31:00']['close'], 99.75)

    def test_missing_minute_and_float_timestamp_are_rejected(self):
        for mutate in (lambda s: (s['timestamps_ns'].pop(10), s['prices'].pop(10)),
                       lambda s: s.update(timestamps_ns=[float(t) for t in s['timestamps_ns']])):
            plan, _, raw, _, _ = fixture()
            mutate(raw[plan['evaluation_dates'][0]])
            with self.assertRaises(ValueError):
                raw_minute_closes(raw, plan['evaluation_dates'])

    def test_band_tampering_and_native_close_disagreement_fail(self):
        for change in ('band', 'close'):
            plan, doc, raw, _, norm = fixture(True)
            i = next(i for i, s in enumerate(doc['output']) if s.startswith('BAR ') and 'T09:52:00 ' in s)
            if change == 'band':
                doc['output'][i] = doc['output'][i].replace('mean=', 'mean=9')
            else:
                raw[plan['evaluation_dates'][0]]['prices'][0] = 100.25
            with self.assertRaises(ValueError):
                reconcile_bars_and_entries(doc['output'], norm, raw, plan['evaluation_dates'])

    def test_missing_first_eligible_entry_detected_even_when_no_native_signals(self):
        plan, doc, raw, _, _ = fixture(True)
        output = [line for line in doc['output'] if not line.startswith('SIGNAL ')]
        with self.assertRaisesRegex(ValueError, 'Missing eligible entry'):
            reconcile_bars_and_entries(output, [], raw, plan['evaluation_dates'])

    def test_reordered_duplicate_or_missing_bar_fails(self):
        for kind in ('missing', 'duplicate', 'reorder'):
            plan, doc, raw, _, _ = fixture()
            if kind == 'missing':
                doc['output'].pop(1)
            elif kind == 'duplicate':
                doc['output'].insert(1, doc['output'][0])
            else:
                doc['output'][0], doc['output'][1] = doc['output'][1], doc['output'][0]
            with self.assertRaises(ValueError):
                reconcile_bars_and_entries(doc['output'], [], raw, plan['evaluation_dates'])

    def test_altered_plan_and_unbound_instance_fail_before_performance(self):
        for which in ('plan', 'instance'):
            plan, doc, raw, binding, _ = fixture()
            if which == 'plan':
                plan['request']['inputs']['BandLength'] = 21
            else:
                binding['observed_instance'] = 'restarted'
            result = assess_postrun(plan, doc, raw, binding)
            self.assertTrue(result['errors'])
            self.assertFalse(result['performance_evaluated'])
            self.assertNotIn('costs', result)

    def test_audit_before_bars_is_not_independent_evidence(self):
        plan, doc, raw, binding, _ = fixture()
        audits = [s for s in doc['output'] if s.startswith('AUDIT ')]
        doc['output'] = audits + [s for s in doc['output'] if not s.startswith('AUDIT ')]
        result = assess_postrun(plan, doc, raw, binding)
        self.assertTrue(result['errors'])
        self.assertIn('AUDIT/snapshot', result['errors'][0])
        self.assertFalse(result['component_reconciliation_passed'])

    def test_absent_signal_at_same_bar_exit_does_not_invent_callback_order(self):
        plan, doc, raw, _, norm = fixture(True, exit_on_cross_bar=True)
        with self.assertRaisesRegex(ValueError, 'ordering unresolved around same-bar exit'):
            reconcile_bars_and_entries(doc['output'], norm, raw, plan['evaluation_dates'])

    def test_inputs_are_not_mutated(self):
        args = fixture(True)[:4]
        before = copy.deepcopy(args)
        assess_postrun(*args)
        self.assertEqual(args, before)

    def test_same_timestamp_last_price_match_does_not_prove_execution(self):
        plan, _, raw, _, norm = fixture(True)
        evidence = observed_last_fill_evidence(norm, raw)
        self.assertTrue(all(e['fill_price_present_at_same_timestamp'] for e in evidence['events']))
        self.assertFalse(evidence['execution_order_proven'])


if __name__ == '__main__':
    unittest.main()
