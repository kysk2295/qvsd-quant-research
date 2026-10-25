import copy
import unittest
from research.prospective_execution_contract import phase_readiness, native_identity, POSTRUN

DATES = ['2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-10-30',
         '2026-11-02','2026-11-03','2026-11-04','2026-11-05','2026-11-06']


def fixture():
    request = dict(strategy='CodexBollingerClock', instrument='NQ DEC26',
        barsPeriod=dict(type='Minute', value=1), inputs=dict(BandLength=20, FirstDate=20261026, LastDate=20261106),
        tickReplay=False, breakAtEod=True, fillResolution='High', fillResolutionType='Tick',
        fillResolutionValue=1, slippageTicks=2, includeCommission=False, includeTradeHistory=True,
        **{'from':'2026-10-25','to':'2026-11-07'})
    doc = dict(id='b1', state='done', error=None, strategy=request['strategy'], instrument=request['instrument'],
        inputs=copy.deepcopy(request['inputs']), tickReplay=False, breakAtEod=True, period='1 Minute',
        settings={k: request[k] for k in ('fillResolution','fillResolutionType','fillResolutionValue',
                                          'slippageTicks','includeCommission','includeTradeHistory')},
        timeZone='Korea Standard Time', warnings=[], outputNote=None,
        trades=[], summary=dict(trades=0), output=[f'AUDIT {d.replace("-", "")} bars=390 gap=False entries=0' for d in DATES],
        **{'from':'2026-10-25T00:00:00','to':'2026-11-07T23:59:59'})
    doc['settings']['maxTrades'] = 0
    return dict(request=request, evaluation_dates=DATES[:]), doc


class ContractTests(unittest.TestCase):
    def validate(self, plan, doc, observed='instance1'):
        result = native_identity(plan, doc, 'b1', 'instance1', observed, 'Korea Standard Time')
        self.assertFalse(result['strategy_validated'])
        self.assertFalse(result['performance_evaluated'])
        self.assertFalse(result['postrun_parity_complete'])
        return result

    def test_future_outputs_are_postrun_not_preconditions(self):
        draft = dict(unmet_reasons=[dict(code=c) for c in (*POSTRUN, 'decision_time', 'no_outcome_inspection')])
        before = copy.deepcopy(draft)
        result = phase_readiness(draft)
        pre = {r['code'] for r in result['pre_run_unmet']}
        self.assertFalse(set(POSTRUN) & pre)
        self.assertIn('decision_time', pre)
        self.assertIn('no_outcome_inspection', pre)
        self.assertFalse(result['ready_for_native'])
        self.assertEqual(before, draft)

    def test_malformed_draft_and_all_green_still_not_authorized(self):
        self.assertTrue(phase_readiness({})['pre_run_unmet'])
        self.assertFalse(phase_readiness(dict(unmet_reasons=[]))['ready_for_native'])

    def test_exact_high_tick1_identity_is_only_partial_evidence(self):
        plan, doc = fixture()
        result = self.validate(plan, doc)
        self.assertTrue(result['identity_and_settings_passed'])

    def test_standard_fill_and_silent_setting_changes_rejected(self):
        for field, value in [('fillResolution','Standard'), ('fillResolutionValue',True),
                             ('slippageTicks',4), ('includeTradeHistory',False), ('maxTrades',50)]:
            plan, doc = fixture(); doc['settings'][field] = value
            self.assertFalse(self.validate(plan, doc)['identity_and_settings_passed'])

    def test_restarted_instance_or_wrong_id_never_matches(self):
        plan, doc = fixture()
        self.assertIn('engine_instance', self.validate(plan, doc, 'instance2')['errors'])
        doc['id'] = 'b2'
        self.assertIn('native_id', self.validate(plan, doc)['errors'])

    def test_request_dates_and_inputs_must_match(self):
        for field, value in [('from','2026-10-26T00:00:00'), ('period','5 Minute'),
                             ('inputs',dict(BandLength=30)), ('tickReplay',True)]:
            plan, doc = fixture(); doc[field] = value
            self.assertFalse(self.validate(plan, doc)['identity_and_settings_passed'])

    def test_output_and_history_incomplete_rejected(self):
        for mutation in (lambda d: d.update(outputNote='truncated'),
                         lambda d: d['summary'].update(trades=1),
                         lambda d: d.update(warnings=['missing data']),
                         lambda d: d['output'].pop(),
                         lambda d: d['output'].append(d['output'][0])):
            plan, doc = fixture(); mutation(doc)
            self.assertFalse(self.validate(plan, doc)['identity_and_settings_passed'])

    def test_session_gap_entry_cap_order_error_rejected(self):
        for line in ('AUDIT 20261026 bars=389 gap=False entries=0',
                     'AUDIT 20261026 bars=390 gap=True entries=0',
                     'AUDIT 20261026 bars=390 gap=False entries=5', 'ORDER_ERROR rejected'):
            plan, doc = fixture(); doc['output'][0] = line
            self.assertFalse(self.validate(plan, doc)['identity_and_settings_passed'])

    def test_running_failed_missing_or_malformed_response_not_success(self):
        for doc in ({}, [], dict(state='running'), dict(state='failed',error='failure')):
            plan, _ = fixture()
            self.assertFalse(self.validate(plan, doc)['identity_and_settings_passed'])

    def test_malformed_dates_and_nested_types_fail_closed(self):
        for replacement in ([20261026] * 10, [f'2026-99-{d:02d}' for d in range(10, 20)], DATES[::-1]):
            plan, doc = fixture(); plan['evaluation_dates'] = replacement
            self.assertFalse(self.validate(plan, doc)['identity_and_settings_passed'])
        plan, doc = fixture(); doc['inputs']['BandLength'] = 20.0
        self.assertIn('inputs', self.validate(plan, doc)['errors'])
        plan, doc = fixture(); plan['request']['barsPeriod']['value'] = True
        self.assertFalse(self.validate(plan, doc)['identity_and_settings_passed'])

    def test_time_zone_must_match_bound_preflight_evidence(self):
        plan, doc = fixture(); doc['timeZone'] = 'Unknown Zone'
        self.assertIn('native_time_zone', self.validate(plan, doc)['errors'])
        plan, doc = fixture()
        self.assertIn('preflight_time_zone_missing', native_identity(plan, doc, 'b1', 'instance1', 'instance1')['errors'])


if __name__ == '__main__':
    unittest.main()
