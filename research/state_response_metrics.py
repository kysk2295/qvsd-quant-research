"""Point-in-time features and separate future labels for a fixed event study."""
import math
from statistics import mean, median
from research.market_state_metrics import bucket_metrics, distribution


def ranks(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [None]*len(values)
    i = 0
    while i < len(order):
        j = i+1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        for k in order[i:j]:
            result[k] = (i+j-1)/2+1
        i = j
    return result


def spearman(xs, ys):
    if len(xs) != len(ys):
        raise ValueError('Paired vectors required')
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if any(not math.isfinite(x) or not math.isfinite(y) for x, y in pairs):
        raise ValueError('Nonfinite pair')
    if len(pairs) < 3:
        return dict(rho=None, pairs=len(pairs), reason='fewer_than3_pairs')
    x, y = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    mx, my = mean(x), mean(y)
    xx, yy = sum((a-mx)**2 for a in x), sum((b-my)**2 for b in y)
    if not xx or not yy:
        return dict(rho=None, pairs=len(pairs), reason='constant_vector')
    rho = sum((a-mx)*(b-my) for a, b in zip(x, y))/math.sqrt(xx*yy)
    return dict(rho=max(-1.0, min(1.0, rho)), pairs=len(pairs), reason=None)


def window_state(bars):
    if len(bars) != 30:
        raise ValueError('Exactly30 closed minutes required')
    metrics = bucket_metrics(bars)
    return dict(rms=metrics['rms_log_move_bps'], net_points=metrics['net_points'],
                signed_efficiency=metrics['net_points']/metrics['close_path_points'] if metrics['close_path_points'] else None,
                log_move_bps=10000*math.log(bars[-1]['close']/bars[0]['open']))


def features(prefix, decision, references, current_date):
    """Receives only bars strictly before decision and five fully earlier dates."""
    if len(references) != 5 or len({r['date'] for r in references}) != 5:
        raise ValueError('Five distinct prior-session references required')
    if any(r['date'] >= current_date or r['clock'] != decision for r in references):
        raise ValueError('Same-clock, strictly earlier-date references required')
    if any(int(m) >= decision for m in prefix):
        raise ValueError('Future/current decision-minute data supplied to features')
    past = window_state([prefix[str(m)] for m in range(decision-30, decision)])
    ref_past = median(r['past_rms'] for r in references)
    ref_future = median(r['future_rms'] for r in references)
    if any(not math.isfinite(v) or v < 0 for r in references for v in (r['past_rms'], r['future_rms'])):
        raise ValueError('Invalid reference movement')
    relative = past['rms']/ref_past if ref_past > 0 else None
    forecast = ref_future*relative if ref_future > 0 and relative is not None else None
    return dict(past_rms=past['rms'], signed_efficiency=past['signed_efficiency'],
                past_net_points=past['net_points'], relative_past_rms=relative,
                reference_past_rms=ref_past, reference_future_rms=ref_future,
                forecast_rms=forecast, control_rms=ref_future if ref_future > 0 else None,
                reference_dates=[r['date'] for r in references], feature_last_minute=decision-1)


def response(future_bars, snapshot):
    """Future labels never modify the frozen feature/forecast snapshot."""
    future = window_state(future_bars)
    ref = snapshot['reference_future_rms']
    past_net = snapshot['past_net_points']
    aligned = None if past_net == 0 else (1 if past_net > 0 else -1)*future['net_points']
    return dict(future_rms=future['rms'], future_log_move_bps=future['log_move_bps'],
                future_net_points=future['net_points'], relative_future_rms=future['rms']/ref if ref > 0 else None,
                continuation='undefined_past_direction' if aligned is None else
                    'continued' if aligned > 0 else 'reversed' if aligned < 0 else 'neutral',
                forecast_absolute_error=abs(future['rms']-snapshot['forecast_rms']) if snapshot['forecast_rms'] is not None else None,
                control_absolute_error=abs(future['rms']-snapshot['control_rms']) if snapshot['control_rms'] is not None else None)


def extract_event(session, decision, references, current_date):
    prefix = {k: v for k, v in session.items() if int(k) < decision}
    snapshot = features(prefix, decision, references, current_date)
    future = [session[str(m)] for m in range(decision+1, decision+31)]
    return snapshot, response(future, snapshot)


def event_summary(rows):
    counts = {key:sum(r['continuation'] == key for r in rows)
              for key in ('continued','reversed','neutral','undefined_past_direction')}
    eligible = len(rows)-counts['undefined_past_direction']
    errors = [(r['forecast_absolute_error'], r['control_absolute_error']) for r in rows
              if r['forecast_absolute_error'] is not None and r['control_absolute_error'] is not None]
    return dict(events=len(rows),
        h1=spearman([r['signed_efficiency'] for r in rows], [r['future_log_move_bps'] for r in rows]),
        h2=spearman([r['relative_past_rms'] for r in rows], [r['relative_future_rms'] for r in rows]),
        continuation_counts=counts, continuation_eligible=eligible,
        continuation_fraction=counts['continued']/eligible if eligible else None,
        forecast_pairs=len(errors), forecast_mae=mean(a for a, b in errors) if errors else None,
        control_mae=mean(b for a, b in errors) if errors else None,
        mae_improvement=mean(b-a for a, b in errors) if errors else None)


def day_summary(days):
    def avg(key):
        values = [d[key] for d in days if d[key] is not None]
        return mean(values) if values else None
    return dict(days=len(days),
        h1_daily_rho=distribution([d['h1']['rho'] for d in days]),
        h2_daily_rho=distribution([d['h2']['rho'] for d in days]),
        h1_positive_days=sum(d['h1']['rho'] is not None and d['h1']['rho'] > 0 for d in days),
        h2_positive_days=sum(d['h2']['rho'] is not None and d['h2']['rho'] > 0 for d in days),
        daily_continuation_fraction=distribution([d['continuation_fraction'] for d in days]),
        daily_mae_improvement=distribution([d['mae_improvement'] for d in days]),
        mean_forecast_mae=avg('forecast_mae'), mean_control_mae=avg('control_mae'),
        mean_mae_improvement=avg('mae_improvement'),
        improved_error_days=sum(d['mae_improvement'] is not None and d['mae_improvement'] > 0 for d in days),
        forecast_pairs=sum(d['forecast_pairs'] for d in days))
