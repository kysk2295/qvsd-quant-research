"""Pure, partial post-run reconciliation of the frozen prospective experiment.

No file loading, transport, production release, or acceptance of a strategy.
Caller-supplied data/identity are not authenticated here. These functions may
only evaluate the reserved market outcomes after the frozen decision gate is
actually satisfied. This preparation batch invokes them on synthetic data only.
"""
import hashlib
import json
import math
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

from research.prospective_clock import local_stamp_ns, reconcile_clocks
from research.prospective_cost_path import assess_cost_path
from research.prospective_execution_contract import native_identity

FROZEN_PLAN_HASH = '25a1f2e7e137b797f36a3424779f6aa0bfeb2ccc16c9ae8d37f85fb38cd6cc00'
MINUTE = 60 * 10**9
NY = ZoneInfo('America/New_York')
BAR = re.compile(r'BAR (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}) close=(\S+) mean=(\S+) lower=(\S+) upper=(\S+) side=(-1|0|1)')
SIGNAL = re.compile(r'SIGNAL (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}) side=(L|S) close=(\S+) mean=(\S+) lower=(\S+) upper=(\S+)')
PENDING = [
    'Authoritative decision-time/no-peek/attempt-ledger and production release evidence',
    'Actual source, installed compiled strategy and data hashes before/after the bound run',
    'Independent source completeness and NinjaTrader import/cache parity',
    'Exit order submission, cancellation and stop-trigger/fill causality: source logs lack individual exit submissions',
    'Permitted forward execution evidence and longer independent validation',
]


def raw_minute_closes(last_by_date, dates):
    """Preserve input event order; boundary ticks belong to [start,end).

    Matches installed NT minute tick aggregation, not a timestamp offset hack.
    Complete minute occupancy alone does not prove a complete exchange tape.
    """
    if not isinstance(last_by_date, dict) or set(last_by_date) != set(dates):
        raise ValueError('Exact reserved Last date keys required')
    result = {}
    for day in dates:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError('Canonical date required')
        raw = last_by_date[day]
        ts0 = np.asarray(raw['timestamps_ns'])
        px = np.asarray(raw['prices'], dtype=float)
        if (ts0.ndim != 1 or ts0.dtype.kind not in 'iu' or px.ndim != 1
                or len(ts0) != len(px) or not len(ts0)):
            raise ValueError('Nonempty integer timestamp / price vectors required')
        if np.any(ts0 > np.iinfo(np.int64).max):
            raise ValueError('Timestamp outside int64')
        ts = ts0.astype(np.int64, copy=False)
        if (np.any(ts[1:] < ts[:-1]) or np.any(ts % 100)
                or not np.all(np.isfinite(px)) or np.any(px <= 0)
                or np.any(px * 4 != np.rint(px * 4))):
            raise ValueError('Ordered 100ns timestamps and finite NQ tick prices required')
        start = local_stamp_ns(day + 'T09:30:00', 'America/New_York')
        for minute in range(390):
            left, end = start + minute * MINUTE, start + (minute + 1) * MINUTE
            a, b = int(np.searchsorted(ts, left)), int(np.searchsorted(ts, end))
            if a == b:
                raise ValueError('Missing raw RTH minute: ' + day + ' ' + str(minute))
            label = (datetime.combine(date.fromisoformat(day), time(9, 30))
                     + timedelta(minutes=minute + 1)).isoformat()
            result[label] = dict(date=day, close=float(px[b-1]), utc_ns=end)
    return result


def reconcile_bars_and_entries(output, normalized, last_by_date, dates):
    """Recalculate closes/bands/crosses and all eligible *entry* decisions.

    Execution/submit output indexes reconstruct position/pending state at each
    BAR callback, including equal timestamps. They do not prove market-event
    versus fill ordering, nor establish unlogged exit-order causality.
    """
    expected = raw_minute_closes(last_by_date, dates)
    bars, signals = [], []
    for index, line in enumerate(output):
        if line.startswith('BAR '):
            m = BAR.fullmatch(line)
            if not m:
                raise ValueError('Malformed BAR output')
            stamp, *numbers, side = m.groups()
            values = dict(zip(('close', 'mean', 'lower', 'upper'), map(float, numbers)))
            if not all(math.isfinite(v) for v in values.values()):
                raise ValueError('Nonfinite BAR value')
            bars.append(dict(stamp=stamp, index=index, side=int(side), **values))
        elif line.startswith('SIGNAL '):
            m = SIGNAL.fullmatch(line)
            if not m:
                raise ValueError('Malformed SIGNAL output')
            stamp, side, *numbers = m.groups()
            values = dict(zip(('close', 'mean', 'lower', 'upper'), map(float, numbers)))
            if not all(math.isfinite(v) for v in values.values()):
                raise ValueError('Nonfinite SIGNAL value')
            signals.append(dict(stamp=stamp, index=index, side=side, **values))
    if [b['stamp'] for b in bars] != list(expected):
        raise ValueError('Missing, duplicated, reordered or unexpected BAR labels')
    # The two component parsers must not accept disconnected evidence: the
    # source emits a contiguous cumulative snapshot after its 16:00 BAR, then
    # AUDIT. An execution callback may print between that BAR and the snapshot.
    covered_snapshot_indexes = set()
    for day in dates:
        audit_indexes = [i for i, line in enumerate(output) if line.startswith('AUDIT ' + day.replace('-', '') + ' ')]
        if len(audit_indexes) != 1:
            raise ValueError('Exactly one daily AUDIT required')
        ai = audit_indexes[0]
        last_bar = next(b['index'] for b in bars if b['stamp'] == day + 'T16:00:00')
        next_bar = next((b['index'] for b in bars if b['index'] > last_bar), len(output))
        first_snapshot = ai
        while first_snapshot > 0 and output[first_snapshot-1].startswith('CLOCK_TRADE|'):
            first_snapshot -= 1
        if not last_bar < first_snapshot <= ai < next_bar:
            raise ValueError('AUDIT/snapshot not after its 16:00 BAR and before next BAR')
        if any(not line.startswith('CLOCK_EXEC|') for line in output[last_bar+1:first_snapshot]):
            raise ValueError('Unexpected output between final BAR and cumulative snapshot')
        covered_snapshot_indexes.update(range(first_snapshot, ai))
    if covered_snapshot_indexes != {i for i, line in enumerate(output) if line.startswith('CLOCK_TRADE|')}:
        raise ValueError('CLOCK_TRADE outside end-of-day snapshot block')
    if len(signals) != len(normalized):
        raise ValueError('SIGNAL / normalized trade count differs')
    by_ns = {}
    for s, t in zip(signals, normalized):
        ns = local_stamp_ns(s['stamp'], 'America/New_York')
        if (ns in by_ns or ns != t['signal_utc_ns'] or s['index'] != t['signal_output_index']
                or s['side'] != t['entry_name']):
            raise ValueError('Signal normalization mismatch')
        by_ns[ns] = (s, t)
    windows, prior, day = [], None, None
    checked = []
    for index, bar in enumerate(bars):
        raw = expected[bar['stamp']]
        if bar['close'] != raw['close']:
            raise ValueError('Raw Last / native close mismatch: ' + bar['stamp'])
        if raw['date'] != day:
            day, windows, prior = raw['date'], [], None
        windows.append(raw['close'])
        windows = windows[-20:]
        direction = 0
        if len(windows) == 20:
            mean = sum(windows) / 20
            dev = 2 * math.sqrt(sum((x - mean)**2 for x in windows) / 20)
            lower, upper = mean - dev, mean + dev
            if prior is not None:
                direction = (1 if prior[0] <= prior[1] and raw['close'] > lower
                             else -1 if prior[0] >= prior[2] and raw['close'] < upper else 0)
            prior = (raw['close'], lower, upper)
        else:
            mean = lower = upper = 0
        if (bar['side'] != direction or any(abs(bar[k] - value) > 1e-7 for k, value
                in (('mean', mean), ('lower', lower), ('upper', upper)))):
            raise ValueError('Independent band/cross mismatch: ' + bar['stamp'])
        daily = [t for t in normalized if t['date'] == day]
        actual = by_ns.get(raw['utc_ns'])
        next_index = bars[index+1]['index'] if index+1 < len(bars) else len(output)
        # The source checks entry after calling its exit method. If a callback
        # prints between BAR and SIGNAL, use the state observed before SIGNAL.
        # With no SIGNAL, the entry-check instant is unlogged; do not guess a
        # before/after order when an exit in this interval changes eligibility.
        cutoff = actual[0]['index'] if actual else bar['index']
        pending_or_open = any(t['submit_output_index'] < cutoff <= t['exit_output_index'] for t in daily)
        entries = sum(t['submit_output_index'] < cutoff for t in daily)
        realized = sum(t['gross_pnl'] - 10 for t in daily if t['exit_output_index'] < cutoff)
        local_time = bar['stamp'][11:]
        eligible = ('09:51:00' <= local_time <= '15:25:00' and not pending_or_open
                    and entries < 4 and realized > -900 and direction != 0)
        if (not actual and '09:51:00' <= local_time <= '15:25:00' and direction != 0 and entries < 4
                and any(bar['index'] < t['exit_output_index'] < next_index for t in daily)):
            after_realized = sum(t['gross_pnl'] - 10 for t in daily if t['exit_output_index'] < next_index)
            after_open = any(t['submit_output_index'] < next_index <= t['exit_output_index'] for t in daily)
            after_eligible = not after_open and after_realized > -900
            if bool(eligible) != bool(after_eligible):
                raise ValueError('Entry decision ordering unresolved around same-bar exit')
        if bool(actual) != eligible:
            raise ValueError('Missing eligible entry or unexpected entry: ' + bar['stamp'])
        if actual:
            s, trade = actual
            if (not bar['index'] < s['index'] < trade['submit_output_index'] < next_index
                    or s['side'] != ('L' if direction == 1 else 'S')
                    or any(s[k] != bar[k] for k in ('close', 'mean', 'lower', 'upper'))):
                raise ValueError('Signal values/order disagree with source BAR')
            checked.append(dict(date=day, signal_utc_ns=raw['utc_ns'],
                previous_entries=entries, realized_after10fee_before_submission=realized))
    return dict(raw_bar_band_cross_parity=True, entry_decision_parity=True,
        verified_bars=len(bars), verified_entries=len(checked), entry_checks=checked,
        bar_convention='Last event in each [09:30+i minutes,09:31+i minutes); ties retain input order',
        exit_order_causality_verified=False)


def observed_last_fill_evidence(trades, last_by_date):
    """Diagnostic price presence only. Never infer executable quotes or slippage."""
    rows = []
    for t in trades:
        raw = last_by_date[t['date']]
        ts, px = np.asarray(raw['timestamps_ns']), np.asarray(raw['prices'])
        for kind in ('entry', 'exit'):
            ns, price = t[kind + '_utc_ns'], t[kind + '_price']
            a, b = int(np.searchsorted(ts, ns, 'left')), int(np.searchsorted(ts, ns, 'right'))
            rows.append(dict(kind=kind, utc_ns=ns, same_timestamp_last_count=b-a,
                fill_price_present_at_same_timestamp=bool(np.any(px[a:b] == price))))
    return dict(events=rows, execution_order_proven=False,
        limitation='Price membership in same-timestamp Last observations is descriptive, not proof of first causal fill, bid/ask execution or realized 2-tick slippage.')


def assess_postrun(plan, document, last_by_date, binding):
    """Check supplied evidence; never authenticate it or call a passing strategy."""
    result = dict(strategy_validated=False, postrun_parity_complete=False,
        production_executor_released=False, actual_evidence_authenticated=False,
        component_reconciliation_passed=False, performance_evaluated=False,
        errors=[], pending_evidence=PENDING[:], decision='incomplete_evidence')
    try:
        digest = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        if digest != FROZEN_PLAN_HASH:
            raise ValueError('Frozen plan differs; this evaluator cannot reinterpret another experiment')
        if (not isinstance(binding, dict) or set(binding) !=
                {'job_id', 'expected_instance', 'observed_instance', 'native_time_zone'}):
            raise ValueError('Explicit complete identity binding required')
        identity = native_identity(plan, document, binding['job_id'], binding['expected_instance'],
                                   binding['observed_instance'], binding['native_time_zone'])
        result['identity'] = identity
        if not identity['identity_and_settings_passed']:
            raise ValueError('Native identity/settings/session evidence failed')
        dates = plan['evaluation_dates']
        clock = reconcile_clocks(document['output'], document['trades'], dates, binding['native_time_zone'])
        result['clock'] = clock
        result['entries'] = reconcile_bars_and_entries(document['output'], clock['trades'], last_by_date, dates)
        costs = assess_cost_path(clock['trades'], dates, last_by_date)
        result.update(costs=costs, performance_evaluated=True,
            observed_last_fill_evidence=observed_last_fill_evidence(clock['trades'], last_by_date))
        result['component_reconciliation_passed'] = bool(clock['passed'] and costs['path_evidence_complete'])
        if not clock['trades']:
            result['decision'] = 'condition_absent_not_performance_evaluable'
            result['performance_evaluated'] = False
        elif not costs['path_evidence_complete']:
            result['decision'] = 'incomplete_marked_path_evidence'
        elif costs['cost_gate_passed'] and costs['concentration_gate_passed']:
            result['decision'] = 'economic_gates_passed_pending_external_and_exit_evidence'
        else:
            result['decision'] = 'missed_fixed_economic_gate_in_this_sample_not_family_rejection'
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        result['errors'].append(type(exc).__name__ + ': ' + str(exc))
    return result


# Deliberately no CLI, file loader, automatic authorization or native integration.
