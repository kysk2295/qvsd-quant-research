"""Descriptive bucket statistics. No strategy signals, PnL or optimization."""
import math


def validate_minutes(minutes, start, end):
    if set(minutes) != {str(m) for m in range(start, end)}:
        raise ValueError('Expected complete consecutive minute keys')
    bars = [minutes[str(m)] for m in range(start, end)]
    for bar in bars:
        prices = [bar[k] for k in ('open', 'high', 'low', 'close')]
        if any(isinstance(p, bool) or not isinstance(p, (int, float)) or
               not math.isfinite(p) or p <= 0 or
               not math.isclose(p * 4, round(p * 4), abs_tol=1e-8, rel_tol=0)
               for p in prices):
            raise ValueError('Finite positive quarter-point OHLC required')
        if not bar['low'] <= min(bar['open'], bar['close']) <= max(bar['open'], bar['close']) <= bar['high']:
            raise ValueError('OHLC range inconsistent')
        v = bar['volume']
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 or v != int(v):
            raise ValueError('Positive integer recorded volume required')
    return bars


def bucket_metrics(bars):
    if not bars or len(bars) % 5:
        raise ValueError('Nonempty complete five-minute blocks required')
    previous = bars[0]['open']
    moves, log_moves = [], []
    for bar in bars:
        moves.append(bar['close'] - previous)
        log_moves.append(math.log(bar['close'] / previous))
        previous = bar['close']
    path = sum(abs(x) for x in moves)
    net = bars[-1]['close'] - bars[0]['open']
    five_moves = []
    previous = bars[0]['open']
    for i in range(4, len(bars), 5):
        five_moves.append(bars[i]['close'] - previous)
        previous = bars[i]['close']
    pairs = list(zip(five_moves, five_moves[1:]))
    eligible = sum(a != 0 and b != 0 for a, b in pairs)
    reversals = sum(a * b < 0 for a, b in pairs)
    return dict(minutes=len(bars),
                rms_log_move_bps=10000 * math.sqrt(sum(r*r for r in log_moves) / len(bars)),
                volume=int(sum(b['volume'] for b in bars)),
                volume_per_minute=sum(b['volume'] for b in bars) / len(bars),
                directional_efficiency=abs(net) / path if path else None,
                net_points=net, close_path_points=path,
                five_minute_reversal_fraction=reversals / eligible if eligible else None,
                five_minute_reversals=reversals,
                five_minute_eligible_pairs=eligible,
                five_minute_zero_excluded_pairs=len(pairs) - eligible,
                five_minute_total_pairs=len(pairs))


def distribution(values):
    """Session-weighted quantiles: linear interpolation at (n-1)*p (type 7)."""
    observed = sorted(x for x in values if x is not None)
    if any(not math.isfinite(x) for x in observed):
        raise ValueError('Nonfinite observation')
    def quantile(p):
        if not observed:
            return None
        at = (len(observed) - 1) * p
        lo, hi = math.floor(at), math.ceil(at)
        return observed[lo] + (observed[hi] - observed[lo]) * (at - lo)
    return dict(count=len(observed), missing=len(values) - len(observed),
                median=quantile(.5), q1=quantile(.25), q3=quantile(.75),
                minimum=min(observed) if observed else None,
                maximum=max(observed) if observed else None)
