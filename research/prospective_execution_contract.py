"""Phase separation and native identity validation, without native calls or PnL.

This module is not a production authorization gate. The frozen Bridge still
refuses submissions. Synthetic identity agreement cannot validate a strategy.
"""
import re
from datetime import date, datetime, time

POSTRUN = ('signal_parity', 'clock_parity', 'ledger_parity', 'native_execution_path')
PRE_EXTRA = ('installed_compiled_source_identity', 'native_import_data_parity',
             'current_stop_and_policy_check', 'fresh_engine_instance_and_idle',
             'counted_executor_release')


def phase_readiness(draft):
    """Preserve every unresolved precondition; future run outputs belong after run."""
    pre, post, invalid = [], [], []
    if not isinstance(draft, dict):
        invalid.append(dict(code='invalid_draft'))
        draft = {}
    reasons = draft.get('unmet_reasons')
    if not isinstance(reasons, list):
        invalid.append(dict(code='invalid_unmet_reasons'))
        reasons = []
    for item in reasons:
        if not isinstance(item, dict) or not isinstance(item.get('code'), str):
            invalid.append(dict(code='invalid_reason'))
            continue
        (post if item['code'] in POSTRUN else pre).append(dict(item))
    # Even prior output claims are not evidence for the as-yet unexecuted run.
    requirements = [dict(code=k, status='required_after_bound_native_run') for k in POSTRUN]
    requirements += [dict(code=k, status='required_after_bound_native_run') for k in
                     ('source_data_hashes_after_run', 'fullprecision_last_equity_path',
                      'frozen_fee_tick_cost_gate', 'best_positive_day_removal')]
    pre.extend(invalid)
    pre.extend(dict(code=k, detail='Not established by the metadata draft') for k in PRE_EXTRA)
    return dict(pre_run_unmet=pre, post_run_required=requirements,
                old_draft_post_run_unmet=post, ready_for_native=False,
                production_executor_integrated=False, native_submissions=0,
                strategy_validated=False,
                explanation='The prior draft checks the complete evidence set; its all-evidence boolean is not a submission precondition.')


def _request_time(value, is_end=False):
    if not isinstance(value, str):
        raise ValueError('Request timestamp string required')
    stamp = datetime.fromisoformat(value)
    if len(value) == 10 and is_end:
        stamp = datetime.combine(stamp.date(), time(23, 59, 59))
    return stamp


def _typed_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_typed_equal(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_typed_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def native_identity(plan, document, job_id, expected_instance, observed_instance, expected_time_zone=None):
    """Check a terminal response's identity/settings only; never grade its returns.

    The instance evidence must be obtained by a future trusted transport. This
    pure function cannot authenticate caller-supplied objects or authorize use.
    """
    errors = []

    def same(code, actual, expected):
        if not _typed_equal(actual, expected):
            errors.append(code)

    try:
        if not isinstance(plan, dict) or not isinstance(document, dict):
            raise ValueError('Object inputs required')
        if not isinstance(job_id, str) or not re.fullmatch('[A-Za-z0-9]+', job_id):
            raise ValueError('Bound native job ID required')
        if not isinstance(expected_instance, str) or not expected_instance:
            raise ValueError('Bound engine instance required')
        same('engine_instance', observed_instance, expected_instance)
        same('native_id', document.get('id'), job_id)
        same('terminal_done', document.get('state'), 'done')
        if document.get('error'):
            errors.append('native_error')
        request = plan['request']
        for name in ('strategy', 'instrument', 'inputs', 'tickReplay', 'breakAtEod'):
            same(name, document.get(name), request[name])
        if not _typed_equal(request['barsPeriod'], dict(type='Minute', value=1)):
            raise ValueError('Frozen Minute1 request required')
        same('period', document.get('period'), '1 Minute')
        for field in ('from', 'to'):
            if _request_time(document[field]) != _request_time(request[field], field == 'to'):
                errors.append('requested_' + field)
        settings = document['settings']
        if not isinstance(settings, dict):
            raise ValueError('Native settings object required')
        for field in ('fillResolution', 'fillResolutionType', 'fillResolutionValue',
                      'slippageTicks', 'includeCommission', 'includeTradeHistory'):
            same('settings_' + field, settings.get(field), request[field])
        # Never silently reuse the legacy Standard-fill native_result classifier.
        for field, expected in (('fillResolution', 'High'), ('fillResolutionType', 'Tick'),
                                ('fillResolutionValue', 1)):
            same('frozen_' + field, request[field], expected)
        same('unbounded_trade_history', settings.get('maxTrades'), 0)
        same('no_warnings', document.get('warnings'), [])
        if document.get('outputNote'):
            errors.append('output_may_be_incomplete')
        if not isinstance(expected_time_zone, str) or not expected_time_zone:
            errors.append('preflight_time_zone_missing')
        else:
            same('native_time_zone', document.get('timeZone'), expected_time_zone)
        trades, summary, output = document['trades'], document['summary'], document['output']
        if not isinstance(trades, list) or not isinstance(summary, dict):
            raise ValueError('Trade list and summary required')
        same('complete_trade_count', summary.get('trades'), len(trades))
        if not isinstance(output, list) or not all(isinstance(x, str) for x in output):
            raise ValueError('Output strings required')
        dates = plan['evaluation_dates']
        if (not isinstance(dates, list) or not all(isinstance(d, str) for d in dates)
                or len(dates) != 10 or len(set(dates)) != 10 or dates != sorted(dates)):
            raise ValueError('Ten fixed dates required')
        if any(date.fromisoformat(d).isoformat() != d for d in dates):
            raise ValueError('Canonical ISO dates required')
        audits = {}
        for line in output:
            if 'ORDER_ERROR' in line:
                errors.append('native_order_error')
            if not line.startswith('AUDIT '):
                continue
            match = re.fullmatch(r'AUDIT (\d{8}) bars=(\d+) gap=(True|False) entries=(\d+)', line)
            if not match:
                errors.append('malformed_session_audit')
                continue
            day, bars, gap, entries = match.groups()
            if day in audits:
                errors.append('duplicate_session_audit')
            audits[day] = (bars, gap, entries)
            if int(bars) != 390 or gap != 'False' or int(entries) > 4:
                errors.append('session_coverage_or_entry_cap')
        same('exact_audited_dates', sorted(audits), sorted(d.replace('-', '') for d in dates))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        errors.append('malformed_response: ' + str(exc))
    return dict(identity_and_settings_passed=not errors, errors=errors,
                strategy_validated=False, performance_evaluated=False,
                postrun_parity_complete=False,
                limitation='Readback and session assertions only. Raw data, signals, clocks, trades and equity still require independent reconciliation.')
