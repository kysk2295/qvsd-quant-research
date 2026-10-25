"""Pure frozen-cost/Last-mark review of supplied, normalized simulated trades.

No files, native adapters, downloads, authentication or production release.
The integration layer must bind dates and objects to the frozen ten-day plan.
"""
import calendar
import math
from datetime import date, datetime, time, timezone
from numbers import Integral, Real
from zoneinfo import ZoneInfo

import numpy as np

from research.last_equity_bounds import FillWindow, audit_path

ET = ZoneInfo('America/New_York')
FEES = (5, 10)
TICK_STRESSES = (2, 4)
TICK_VALUE = 5
POINT_VALUE = 20
INITIAL = 150000


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _ns(value, name):
    _require(not isinstance(value, (bool, np.bool_)) and isinstance(value, Integral),
             name + ': integer UTC nanoseconds required')
    value = int(value)
    _require(0 <= value <= np.iinfo(np.int64).max and value % 100 == 0,
             name + ': nonnegative int64 at 100ns resolution required')
    return value


def _number(value, name, price=False):
    _require(not isinstance(value, (bool, np.bool_)) and isinstance(value, Real),
             name + ': finite number required')
    try:
        value = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(name + ': finite number required') from exc
    _require(math.isfinite(value), name + ': finite number required')
    if price:
        _require(value > 0 and math.isfinite(value * 4) and
                 math.isclose(value * 4, round(value * 4), abs_tol=1e-8, rel_tol=0),
                 name + ': positive NQ quarter-point price required')
    return value


def _local(ns):
    # Only calendar membership uses seconds. All ordering/path math retains int ns.
    return datetime.fromtimestamp(ns // 1000000000, timezone.utc).astimezone(ET)


def _session_bounds(day):
    d = date.fromisoformat(day)
    return tuple(calendar.timegm(datetime.combine(d, clock, ET).astimezone(timezone.utc).utctimetuple())
                 * 1000000000 for clock in (time(9, 30), time(16)))


def _closed_dd(nets):
    value = peak = dd = 0.0
    for net in nets:
        value += net
        peak = max(peak, value)
        dd = max(dd, peak - value)
    return dd


def _descriptive(nets):
    wins = [n for n in nets if n > 0]
    losses = [-n for n in nets if n < 0]
    streak = maximum = 0
    for net in nets:
        streak = streak + 1 if net < 0 else 0
        maximum = max(maximum, streak)
    avg_win = sum(wins) / len(wins) if wins else None
    avg_loss = sum(losses) / len(losses) if losses else None
    return dict(trades=len(nets), wins=len(wins), losses=len(losses),
                breakeven=len(nets) - len(wins) - len(losses),
                win_fraction=len(wins) / len(nets) if nets else None,
                average_win=avg_win, average_loss_magnitude=avg_loss,
                realized_payoff_ratio=avg_win / avg_loss if avg_win is not None and avg_loss else None,
                profit_factor=sum(wins) / sum(losses) if losses else None,
                expectancy=sum(nets) / len(nets) if nets else None,
                maximum_loss_streak=maximum,
                undefined_pf='No losing trades means undefined, never infinity or automatic acceptance.')


def _last_arrays(value, day):
    _require(isinstance(value, dict), day + ': Last object required')
    _require('timestamps_ns' in value and 'prices' in value, day + ': Last fields missing')
    raw_ts, raw_px = value['timestamps_ns'], value['prices']
    _require(isinstance(raw_ts, (list, tuple, np.ndarray)) and
             isinstance(raw_px, (list, tuple, np.ndarray)), day + ': Last arrays required')
    _require(np.ndim(raw_ts) == np.ndim(raw_px) == 1 and len(raw_ts) == len(raw_px)
             and len(raw_ts) > 0, day + ': matched nonempty one-dimensional Last arrays required')
    ts = np.asarray([_ns(v, day + ' Last clock') for v in raw_ts], dtype=np.int64)
    px = np.asarray([_number(v, day + ' Last price', price=True) for v in raw_px], dtype=float)
    _require(not np.any(np.diff(ts) < 0), day + ': Last clocks must be ordered; equal clocks retained')
    return ts, px


def _path(ts, prices, windows, fee, expected_net, expected_dd):
    try:
        result = audit_path(ts, prices, windows, fee, initial=INITIAL, point_value=POINT_VALUE)
    except (AssertionError, TypeError, OverflowError) as exc:
        raise ValueError('Last-path validation failed: ' + str(exc)) from exc
    result.pop('path')  # No large arrays in the evidence document.
    _require(math.isclose(result['net'], expected_net, abs_tol=1e-7, rel_tol=0),
             'Last-path final net differs from ledger')
    _require(math.isclose(result['closed_trade_drawdown'], expected_dd, abs_tol=1e-7, rel_tol=0),
             'Last-path closed DD differs from ledger')
    result['status'] = 'bounded_observed_last_path'
    return result


def assess_cost_path(trades, dates, last_by_date):
    """Validate inputs and return fixed-cost gates plus conditional Last DD bounds.

    Any nonempty ordered weekday date list is supported for synthetic fixtures;
    the production caller must require the exact frozen ten dates. Tied exit and
    next-entry clocks are structurally possible but unsupported by the preserved
    path solver, so they produce explicit unresolved path evidence, not fabricated
    ordering. Other malformed, overlapping or inconsistent input raises ValueError.
    """
    _require(isinstance(dates, (list, tuple)) and dates and all(type(d) is str for d in dates),
             'Nonempty ISO date list required')
    dates = list(dates)
    _require(dates == sorted(set(dates)), 'Dates must be unique and chronologically ordered')
    for day in dates:
        try:
            parsed = date.fromisoformat(day)
        except (ValueError, TypeError) as exc:
            raise ValueError('Invalid ISO date') from exc
        _require(parsed.isoformat() == day and parsed.weekday() < 5, 'Canonical weekday date required')
    _require(isinstance(last_by_date, dict) and set(last_by_date) == set(dates),
             'Last inputs must contain exactly the declared dates, including zero-trade days')
    _require(isinstance(trades, (list, tuple)), 'Trade list required')
    arrays = {day: _last_arrays(last_by_date[day], day) for day in dates}
    normalized, by_day, windows = [], {day: [] for day in dates}, {day: [] for day in dates}
    previous_exit = None
    seen = set()
    gate_checks = []
    realized = {day: 0.0 for day in dates}
    tied_dates = set()
    required = ('date', 'side', 'qty', 'entry_name', 'exit_name', 'signal_utc_ns',
                'entry_utc_ns', 'exit_utc_ns', 'entry_price', 'exit_price', 'gross_pnl')
    for original in trades:
        _require(isinstance(original, dict) and all(k in original for k in required),
                 'Normalized trade fields missing')
        row = dict(original)
        day = row['date']
        _require(type(day) is str and day in by_day, 'Trade outside declared dates')
        _require(row['side'] in ('Long', 'Short'), 'Long/Short side required')
        _require(not isinstance(row['qty'], (bool, np.bool_)) and
                 isinstance(row['qty'], Integral) and int(row['qty']) == 1, 'Exactly one NQ required')
        row['qty'] = 1
        _require(row['entry_name'] == ('L' if row['side'] == 'Long' else 'S'), 'Entry name/side mismatch')
        _require(isinstance(row['exit_name'], str) and row['exit_name'].strip(), 'Exit name required')
        for k in ('signal_utc_ns', 'entry_utc_ns', 'exit_utc_ns'):
            row[k] = _ns(row[k], k)
        signal, entry, exit_ = (row[k] for k in ('signal_utc_ns', 'entry_utc_ns', 'exit_utc_ns'))
        _require(signal <= entry <= exit_, 'Signal/entry/exit causal order invalid')
        session_open, session_close = _session_bounds(day)
        for stamp in (signal, entry, exit_):
            local = _local(stamp)
            _require(local.date().isoformat() == day and session_open <= stamp <= session_close,
                     'Trade/signal outside same-day ET RTH; no overnight allowed')
        _require(previous_exit is None or entry >= previous_exit, 'Trade order or holding windows overlap')
        if previous_exit is not None and entry == previous_exit:
            tied_dates.add(day)
        previous_exit = exit_
        row['entry_price'] = _number(row['entry_price'], 'entry_price', price=True)
        row['exit_price'] = _number(row['exit_price'], 'exit_price', price=True)
        row['gross_pnl'] = _number(row['gross_pnl'], 'gross_pnl')
        direction = 1 if row['side'] == 'Long' else -1
        gross = (row['exit_price'] - row['entry_price']) * POINT_VALUE * direction
        _require(math.isclose(gross, row['gross_pnl'], abs_tol=1e-7, rel_tol=0), 'Gross PnL/price mismatch')
        identity = (entry, exit_, row['side'], row['entry_price'], row['exit_price'])
        _require(identity not in seen, 'Duplicate round trip')
        seen.add(identity)
        _require(len(by_day[day]) < 4, 'More than four entries on a declared day')
        _require(realized[day] > -900, 'Entry after high-fee realized -900 halt')
        gate_checks.append(dict(date=day, entry_utc_ns=entry,
                                before_entry_realized_after10fee=realized[day], entry_permitted=True))
        realized[day] += row['gross_pnl'] - 10
        ts, _ = arrays[day]
        _require(ts[0] < entry and ts[-1] > exit_, 'Last context required before entry and after exit')
        windows[day].append(FillWindow(entry, entry, exit_, exit_, row['entry_price'],
                                       row['exit_price'], direction, 1))
        normalized.append(row)
        by_day[day].append(row)

    # Crop only the held windows plus context when building the account path;
    # full ETH files from adjacent dates may overlap outside these windows.
    pieces_ts, pieces_px, all_windows = [], [], []
    for day in dates:
        if windows[day]:
            ts, px = arrays[day]
            a = int(np.searchsorted(ts, windows[day][0].entry_lo, 'left')) - 1
            b = int(np.searchsorted(ts, windows[day][-1].exit_hi, 'right')) + 1
            pieces_ts.append(ts[a:b]); pieces_px.append(px[a:b]); all_windows.extend(windows[day])
    if not all_windows:
        pieces_ts, pieces_px = [arrays[dates[0]][0]], [arrays[dates[0]][1]]
    aggregate_ts, aggregate_px = np.concatenate(pieces_ts), np.concatenate(pieces_px)
    _require(not np.any(np.diff(aggregate_ts) < 0), 'Cross-date Last context ordering inconsistent')

    fee_cases = {}
    for fee in FEES:
        nets = [t['gross_pnl'] - fee for t in normalized]
        daily_net = {day: sum(t['gross_pnl'] - fee for t in by_day[day]) for day in dates}
        net = sum(nets)
        daily_paths = {}
        for day in dates:
            day_nets = [t['gross_pnl'] - fee for t in by_day[day]]
            if day in tied_dates:
                daily_paths[day] = dict(status='unresolved_equal_timestamp_cross_trade',
                                       reason='Preserved solver rejects next entry at prior exit timestamp; no ordering fabricated.')
            else:
                daily_paths[day] = _path(*arrays[day], windows[day], fee, daily_net[day], _closed_dd(day_nets))
        aggregate = (dict(status='unresolved_equal_timestamp_cross_trade', dates=sorted(tied_dates))
                     if tied_dates else _path(aggregate_ts, aggregate_px, all_windows, fee, net, _closed_dd(nets)))
        stress = {str(ticks): dict(additional_ticks_per_fill=ticks,
                                  incremental_cost=2 * TICK_VALUE * ticks * len(normalized),
                                  net=net - 2 * TICK_VALUE * ticks * len(normalized))
                  for ticks in TICK_STRESSES}
        worst = min(daily_net.values())
        fee_cases[str(fee)] = dict(roundtrip_fee=fee, net=net, daily_net=daily_net,
            closed_trade_drawdown=_closed_dd(nets), descriptive=_descriptive(nets),
            additional_tick_stress=stress, daily_paths=daily_paths, aggregate_path=aggregate,
            worst_closed_day=worst, worst_closed_day_dates=[d for d in dates if daily_net[d] == worst],
            maximum_intraday_loss_from_day_start_lower=(None if tied_dates else
                max(p['worst_loss_from_start_lower'] for p in daily_paths.values())),
            maximum_intraday_loss_from_day_start_upper=(None if tied_dates else
                max(p['worst_loss_from_start_upper'] for p in daily_paths.values())),
            best_positive_day_removed=net - max(0.0, max(daily_net.values())))
    high = fee_cases['10']
    cost_pass = bool(normalized) and high['additional_tick_stress']['4']['net'] > 0
    concentration_pass = bool(normalized) and high['best_positive_day_removed'] > 0
    complete = not tied_dates
    decision = ('not_performance_evaluable' if not normalized else
                'pending_path_evidence' if not complete else
                'economic_gates_passed_pending_other_evidence' if cost_pass and concentration_pass else
                'missed_fixed_gates_in_this_sample')
    return dict(kind='pure_frozen_cost_and_observed_last_path_review', dates=dates,
        unique_trades=len(normalized), zero_trade_dates=[d for d in dates if not by_day[d]],
        fee_cases=fee_cases, realized_entry_gate_checks=gate_checks,
        high_fee_realized_overshoot_beyond900={d: max(0.0, -realized[d] - 900) for d in dates},
        cost_gate_passed=cost_pass, concentration_gate_passed=concentration_pass,
        path_evidence_complete=complete, unresolved_equal_timestamp_cross_trade_dates=sorted(tied_dates),
        decision=decision, strategy_validated=False, strategy_family_rejected=False,
        live_trading_authorized=False, native_submissions=0,
        limitations=[
            'Pure supplied-object review does not authenticate source/deployment, the exact ten frozen dates, or no-peeking evidence.',
            'One recorded native fill path; fees5/10 and extra2/4ticks EACH of two fills are separate arithmetic scenarios, not two native cost variants.',
            'Observed Last path is conditional on fixed fills and supplied stream; source390minute completeness and fill/exit parity are checked separately.',
            'Fees split half at entry/exit. Fullprecision timestamps retain unresolved ordering with equal-time Last events; bounds need not be attainable.',
            'No bid/ask liquidation, queue, impact, changed-execution path, exchange-losslessness or live/account risk-cap certification.',
            'Realized -900 blocks new entries only; final-trade and open losses can exceed it. No new numerical path-risk pass threshold was invented.',
            'Zero-trade days have zero economic return; all-zero observations are not performance evaluable. No Sharpe, confidence or edge claim.',
            'Passing fixed economic gates alone leaves other evidence pending and grants no validation eligibility. Only the separate complete review of data, signal, clock, execution and plan evidence may establish eligibility for longer preregistered validation.'])
