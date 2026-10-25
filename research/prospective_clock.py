"""Pure clock/ledger reconciliation for the frozen CodexBollingerClock output.

No files, native calls, authentication, production permission or strategy verdict.
The native .NET clock has 100ns precision; all UTC timestamps below are integer
Unix nanoseconds divisible by 100. Output order supplies the single-position FIFO
relationship, not an execution id (the source does not print one). Its ordering
relative to Last events at an equal timestamp remains unknown.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_WINDOWS_ZONES = {
    'UTC': 'UTC', 'Eastern Standard Time': 'America/New_York',
    'Central Standard Time': 'America/Chicago', 'Mountain Standard Time': 'America/Denver',
    'US Mountain Standard Time': 'America/Phoenix', 'Pacific Standard Time': 'America/Los_Angeles',
    'Korea Standard Time': 'Asia/Seoul', 'Tokyo Standard Time': 'Asia/Tokyo',
    'China Standard Time': 'Asia/Shanghai', 'India Standard Time': 'Asia/Kolkata',
    'GMT Standard Time': 'Europe/London', 'W. Europe Standard Time': 'Europe/Berlin',
}
_STAMP = re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,7}))?(Z|[+-]\d{2}:\d{2})?')
_SECOND = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
_SIGNAL = re.compile(r'SIGNAL (\S+) side=([LS]) close=(\S+) mean=(\S+) lower=(\S+) upper=(\S+)')
_AUDIT = re.compile(r'AUDIT (\d{8}) bars=(\d+) gap=(True|False) entries=(\d+)')
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_SECOND_NS = 1_000_000_000
_TICKS_PER_SECOND = 10_000_000


def _zone(name):
    if not isinstance(name, str) or not name:
        raise ValueError('An explicit native IANA or supported Windows time zone is required')
    try:
        return ZoneInfo(_WINDOWS_ZONES.get(name, name))
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValueError('Unknown time zone: ' + name) from exc


def _parts(stamp, exact_clock=False):
    match = _STAMP.fullmatch(stamp) if isinstance(stamp, str) else None
    if not match or (exact_clock and len(match[2] or '') != 7):
        raise ValueError('ISO timestamp required, with seven fractional digits for CLOCK records')
    try:
        wall = datetime.fromisoformat(match[1])
    except ValueError as exc:
        raise ValueError('Invalid calendar timestamp') from exc
    fraction_ticks = int((match[2] or '').ljust(7, '0') or '0')
    wall = wall.replace(microsecond=fraction_ticks // 10)
    return wall, fraction_ticks, match[3]


def _stamp_ns(stamp, zone, exact_clock=False):
    wall, fraction_ticks, suffix = _parts(stamp, exact_clock)
    possibilities = []
    for fold in (0, 1):
        aware = wall.replace(tzinfo=zone, fold=fold)
        utc = aware.astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == wall:
            possibilities.append((utc, aware.utcoffset()))
    if not possibilities:
        raise ValueError('Nonexistent local time during DST transition')
    if len({item[1] for item in possibilities}) != 1:
        raise ValueError('Ambiguous local time during DST transition')
    utc, offset = possibilities[0]
    if suffix:
        if suffix == 'Z':
            expected = timedelta(0)
        else:
            hour, minute = int(suffix[1:3]), int(suffix[4:6])
            if hour > 23 or minute > 59:
                raise ValueError('Invalid explicit timestamp offset')
            expected = timedelta(minutes=(hour * 60 + minute) * (1 if suffix[0] == '+' else -1))
        if expected != offset:
            raise ValueError('Explicit offset disagrees with supplied time zone')
    delta = utc - _EPOCH
    ns = (delta.days * 86400 + delta.seconds) * _SECOND_NS + delta.microseconds * 1000
    return ns + (fraction_ticks % 10) * 100


def local_stamp_ns(stamp, time_zone):
    """Convert explicit-zone local ISO text to integer Unix ns, without floats.

    Accepts whole seconds or 1..7 fractional digits. An offset, if present, must
    agree with the supplied zone. Ambiguous/nonexistent wall times are rejected,
    even if an offset was supplied, because the native wall-clock ticks have no
    independent fold bit in the exported evidence.
    """
    return _stamp_ns(stamp, _zone(time_zone))


def _clock(stamp, ticks_text, zone):
    wall, fraction, _ = _parts(stamp, exact_clock=True)
    if not isinstance(ticks_text, str) or not re.fullmatch(r'\d+', ticks_text):
        raise ValueError('Exact integer .NET ticks required')
    ticks = int(ticks_text)
    expected = (((wall.toordinal() - 1) * 86400 + wall.hour * 3600
                 + wall.minute * 60 + wall.second) * _TICKS_PER_SECOND + fraction)
    if ticks != expected:
        raise ValueError('.NET ticks and seven-digit local ISO disagree')
    return dict(local=stamp, wall_ticks=ticks, utc_ns=_stamp_ns(stamp, zone, True))


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError('Invalid numeric ' + field)
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('Invalid numeric ' + field) from exc
    if not number.is_finite() or not math.isfinite(float(number)):
        raise ValueError('Nonfinite or unrepresentable ' + field)
    return number


def _et(ns):
    seconds, rem = divmod(ns, _SECOND_NS)
    return (_EPOCH + timedelta(seconds=seconds, microseconds=rem // 1000)).astimezone(_zone('America/New_York'))


def _dates(values):
    if (not isinstance(values, list) or len(values) != 10
            or not all(isinstance(value, str) for value in values)
            or values != sorted(values) or len(set(values)) != 10):
        raise ValueError('Ten distinct ordered canonical evaluation dates required')
    for value in values:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError('Canonical evaluation dates required')
    return list(values)


def _snapshot_key(entry, exit_):
    return (entry['wall_ticks'], exit_['wall_ticks'], entry['utc_ns'], exit_['utc_ns'])


def reconcile_clocks(output, trades, dates, native_time_zone):
    """Reconcile supplied strings/native trades under strict flat FIFO evidence.

    Returns normalized trades, parsed submissions/executions, audits and explicit
    limitations. Submission timestamps are primary bar labels, not actual order
    wall-clock times. Raises ValueError on inconsistent or incomplete evidence.
    A submission without a matched fill fails reconciliation; it is not silently
    converted into a trade or discarded as a presumed cancellation.
    """
    dates, zone = _dates(dates), _zone(native_time_zone)
    if not isinstance(output, list) or not all(isinstance(line, str) for line in output):
        raise ValueError('Complete output string list required')
    if not isinstance(trades, list) or not all(isinstance(row, dict) for row in trades):
        raise ValueError('Complete native trade object list required')
    submissions, executions, completed, audits = [], [], [], []
    previous_snapshot, snapshot = [], []
    pending_signal = pending_submit = position = None
    last_execution_ns = None
    daily_submits = {day: 0 for day in dates}

    def expected_day(ns):
        day = _et(ns).date().isoformat()
        if len(audits) >= len(dates) or day != dates[len(audits)]:
            raise ValueError('Clock event outside its ordered unaudited evaluation date')
        return day

    for index, line in enumerate(output):
        if 'ORDER_ERROR' in line:
            raise ValueError('Native order error prevents complete execution reconciliation')
        if snapshot and not line.startswith(('CLOCK_TRADE|', 'AUDIT ')):
            raise ValueError('Cumulative CLOCK_TRADE block must end with its AUDIT')
        if line.startswith('SIGNAL'):
            match = _SIGNAL.fullmatch(line)
            if not match or not _SECOND.fullmatch(match[1]):
                raise ValueError('Malformed SIGNAL record')
            ns = local_stamp_ns(match[1], 'America/New_York')
            day, eastern = expected_day(ns), _et(ns)
            minute = eastern.hour * 60 + eastern.minute
            if eastern.second or not 591 <= minute <= 925:
                raise ValueError('Signal outside source entry submission window')
            if pending_signal is not None or pending_submit is not None or position is not None:
                raise ValueError('Signal occurred while a position or submission was pending')
            # SIGNAL and CLOCK_SUBMIT print the primary bar label, not the
            # instant this callback submitted an order. A prior exit callback
            # may have a later fractional clock while appearing earlier in this
            # same bar callback's output. Flat/FIFO output order remains binding.
            fields = [_number(match[n], 'signal numeric field') for n in range(3, 7)]
            pending_signal = dict(date=day, side=match[2], signal_utc_ns=ns,
                                  signal_output_index=index, close=fields[0])
        elif line.startswith('CLOCK_SUBMIT'):
            fields = line.split('|')
            if len(fields) != 5 or fields[0] != 'CLOCK_SUBMIT' or fields[3] not in ('L', 'S'):
                raise ValueError('Malformed CLOCK_SUBMIT record')
            stamp = _clock(fields[1], fields[2], zone)
            close = _number(fields[4], 'submission close')
            day = expected_day(stamp['utc_ns'])
            if (pending_signal is None or pending_submit is not None or position is not None
                    or pending_signal['signal_utc_ns'] != stamp['utc_ns']
                    or pending_signal['side'] != fields[3] or pending_signal['close'] != close):
                raise ValueError('SIGNAL and CLOCK_SUBMIT do not correspond one to one')
            daily_submits[day] += 1
            if daily_submits[day] > 4:
                raise ValueError('Source daily submission cap exceeded')
            pending_submit = {**pending_signal, **stamp, 'close': float(close),
                              'submit_output_index': index}
            submissions.append(pending_submit)
            pending_signal = None
        elif line.startswith('CLOCK_EXEC'):
            fields = line.split('|')
            if len(fields) != 10 or fields[0] != 'CLOCK_EXEC':
                raise ValueError('Malformed CLOCK_EXEC record')
            stamp, callback = _clock(fields[1], fields[2], zone), _clock(fields[3], fields[4], zone)
            primary_ns = _stamp_ns(fields[5], zone, exact_clock=True)
            price = _number(fields[7], 'execution price')
            if (stamp['utc_ns'] != callback['utc_ns'] or stamp['wall_ticks'] != callback['wall_ticks']
                    or fields[8] != '1' or fields[9] != 'Historical' or not fields[6] or price <= 0):
                raise ValueError('Execution callback clock, quantity, state or price mismatch')
            day = expected_day(stamp['utc_ns'])
            if last_execution_ns is not None and stamp['utc_ns'] < last_execution_ns:
                raise ValueError('Execution timestamps are not chronological')
            execution = {**stamp, 'date': day, 'name': fields[6], 'qty': 1,
                         'price': float(price), 'output_index': index,
                         'callback_local': fields[3], 'callback_utc_ns': callback['utc_ns'],
                         'primary_local': fields[5], 'primary_utc_ns': primary_ns,
                         'state': 'Historical'}
            if fields[6] in ('L', 'S'):
                if (position is not None or pending_submit is None or pending_signal is not None
                        or pending_submit['side'] != fields[6] or pending_submit['date'] != day
                        or stamp['utc_ns'] < pending_submit['signal_utc_ns']):
                    raise ValueError('Entry execution lacks its causal flat FIFO submission')
                position = dict(submission=pending_submit, entry=execution)
                pending_submit = None
            else:
                if (position is None or pending_submit is not None or pending_signal is not None
                        or position['entry']['date'] != day
                        or stamp['utc_ns'] < position['entry']['utc_ns']):
                    raise ValueError('Exit execution lacks its same-day open position')
                completed.append({**position, 'exit': execution})
                position = None
            executions.append(execution)
            last_execution_ns = stamp['utc_ns']
        elif line.startswith('CLOCK_TRADE'):
            fields = line.split('|')
            if len(fields) != 5 or fields[0] != 'CLOCK_TRADE':
                raise ValueError('Malformed CLOCK_TRADE record')
            entry, exit_ = _clock(fields[1], fields[2], zone), _clock(fields[3], fields[4], zone)
            snapshot.append(_snapshot_key(entry, exit_))
        elif line.startswith('AUDIT'):
            match = _AUDIT.fullmatch(line)
            if not match or len(audits) >= 10:
                raise ValueError('Malformed or extra AUDIT')
            day = dates[len(audits)]
            if (match[1] != day.replace('-', '') or match[2] != '390' or match[3] != 'False'
                    or int(match[4]) != daily_submits[day] or int(match[4]) > 4):
                raise ValueError('AUDIT dates, coverage, gaps or submission counts disagree')
            if position is not None or pending_submit is not None or pending_signal is not None:
                raise ValueError('AUDIT has an open position or unmatched submission')
            keys = [_snapshot_key(item['entry'], item['exit']) for item in completed]
            if len(snapshot) < len(previous_snapshot) or snapshot[:len(previous_snapshot)] != previous_snapshot:
                raise ValueError('Cumulative trade snapshot lost or changed its prior prefix')
            if snapshot != keys:
                raise ValueError('Cumulative snapshot and FIFO executions disagree in count/order/clocks')
            audits.append(dict(date=day, bars=390, gap=False, entries=int(match[4]),
                               cumulative_trades=len(snapshot), output_index=index))
            previous_snapshot, snapshot = list(snapshot), []
        elif line.startswith('CLOCK_'):
            raise ValueError('Unknown CLOCK record')
        # BAR alignment belongs to the separate signal/rule evaluator. COUNTS
        # diagnostics are not reconciled or treated as evidence by this function.

    if (len(audits) != 10 or snapshot or pending_signal is not None or pending_submit is not None
            or position is not None or len(trades) != len(completed)
            or len(previous_snapshot) != len(trades) or len(submissions) != len(trades)):
        raise ValueError('Missing final audit, unclosed/unfilled order, or truncated native ledger')
    normalized = []
    for native, pair in zip(trades, completed):
        submission, entry, exit_ = pair['submission'], pair['entry'], pair['exit']
        side = 'Long' if entry['name'] == 'L' else 'Short'
        if ('error' in native or native.get('side') != side or type(native.get('qty')) is not int
                or native['qty'] != 1 or native.get('entryName') != entry['name']
                or native.get('exitName') != exit_['name']):
            raise ValueError('Native trade side, quantity or names disagree with FIFO executions')
        for prefix, execution in (('entry', entry), ('exit', exit_)):
            native_stamp = native.get(prefix + 'Time')
            if (not isinstance(native_stamp, str) or not _SECOND.fullmatch(native_stamp)
                    or native_stamp != execution['local'][:19]
                    or local_stamp_ns(native_stamp, native_time_zone) != execution['utc_ns'] // _SECOND_NS * _SECOND_NS
                    or _number(native.get(prefix + 'Price'), 'native price') != _number(execution['price'], 'execution price')):
                raise ValueError('Native whole-second serialization or price disagrees with exact clock')
        gross = (_number(entry['price'], 'entry price') - _number(exit_['price'], 'exit price')) * (-20 if side == 'Long' else 20)
        if abs(_number(native.get('pnl'), 'native gross pnl') - gross) > Decimal('0.00000001'):
            raise ValueError('Native pnl differs from one NQ contract gross price change')
        normalized.append(dict(date=entry['date'], side=side, qty=1, entry_name=entry['name'],
                               exit_name=exit_['name'], signal_utc_ns=submission['signal_utc_ns'],
                               entry_utc_ns=entry['utc_ns'], exit_utc_ns=exit_['utc_ns'],
                               entry_price=entry['price'], exit_price=exit_['price'], gross_pnl=float(gross),
                               signal_output_index=submission['signal_output_index'],
                               submit_output_index=submission['submit_output_index'],
                               entry_output_index=entry['output_index'], exit_output_index=exit_['output_index'],
                               entry_primary_local=entry['primary_local'], exit_primary_local=exit_['primary_local'],
                               entry_primary_utc_ns=entry['primary_utc_ns'], exit_primary_utc_ns=exit_['primary_utc_ns'],
                               entry_wall_ticks=entry['wall_ticks'], exit_wall_ticks=exit_['wall_ticks']))
    return dict(passed=True, trades=normalized, submissions=submissions, executions=executions,
                audits=audits, dates=dates, native_time_zone=zone.key,
                timestamp_unit='unix_ns', clock_precision_ns=100, strategy_validated=False,
                equal_timestamp_last_ordering='unknown',
                limitations=[
                    'Caller-supplied output and trades are not authenticated by this pure function.',
                    'CLOCK_EXEC lacks execution/order ids; mapping depends on complete flat one-contract FIFO output.',
                    'Unfilled or cancelled/rejected submissions cannot be proven from these logs and fail reconciliation.',
                    'SIGNAL/CLOCK_SUBMIT time is the primary bar clock, not an actual submission timestamp or proof of realtime order latency.',
                    'Primary Time[0] is parsed but not matched to a BAR here; it is not the execution clock and no maximum fill delay is imposed.',
                    'Exit names and clocks match the ledger; exit-rule correctness and actual Last-event causality remain separate.',
                    'AUDIT has no timestamp; its BAR placement and actual 390-bar coverage require separate checks, and no extra exit cutoff is invented.',
                    'COUNTS diagnostics are not reconciled by this clock-only function.',
                    'Equal-timestamp execution versus Last ordering remains unknown.',
                ])
