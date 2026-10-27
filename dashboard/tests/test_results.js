'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {recordKind, buildSummaries, researchVerdict, performanceMetrics} = require('../static/results.js');

function sample(overrides = {}) {
  return {candidate: 'nr7', fee_per_roundtrip: 5, dates: ['2026-10-02', '2026-10-05'],
    run_ids: ['run-a'], sources: ['native-ledger'], verdict: 'sample_too_sparse_for_adoption',
    metrics: {net: -245, trades: 1, profit_factor: 0, closed_trade_drawdown: {maximum: 245}, win_rate: 0}, ...overrides};
}
function run(cases = [sample()], overrides = {}) {
  return {id: 'run-a', status: 'completed', phase: 'recent', metrics: {net: -245, trades: 1},
    params: {assessment: {extended_metrics_review: {sha256: 'hash-a', report: 'metrics-review.json', methodology: 'method.md', cases}}}, ...overrides};
}

test('browser global and CommonJS provide the same four pure entry points', () => {
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync(require.resolve('../static/results.js'), 'utf8'), context);
  assert.deepEqual(Object.keys(context.DashboardResults).sort(), ['buildSummaries', 'performanceMetrics', 'recordKind', 'researchVerdict']);
});

test('preparation, data analysis, and empty legacy preparation IDs are research work', () => {
  for (const phase of ['research_preparation', 'data_quality', 'data_analysis', 'hypothesis_research', 'data-audit']) {
    assert.equal(recordKind({phase, metrics: {}}), 'research');
  }
  const prep = {id: 'nq-future-import-preparation-20261025', status: 'completed', metrics: {}};
  assert.equal(recordKind(prep), 'research');
  assert.equal(researchVerdict(prep).label, '작업 완료 · 성과 평가 아님');
  assert.equal(recordKind(run()), 'performance');
  assert.equal(recordKind({id: 'nq-native-abc', phase: 'Native coverage mismatch', metrics: {}}), 'performance');
});

test('repeated reports deduplicate without merging costs, dates, or constituent runs', () => {
  const cases = [sample(), sample({fee_per_roundtrip: 10}), sample({dates: ['2026-10-06']}), sample({run_ids: ['run-b']})];
  const a = run(cases), b = run(cases.map(c => ({...c, dates: [...c.dates].reverse()})), {id: 'run-b'});
  const result = buildSummaries([a, b]);
  assert.equal(result.length, 4);
  assert.equal(new Set(result.map(c => c.id)).size, 4);
  assert.deepEqual(result.map(c => c.metrics.net), [-245, -245, -245, -245]);
  assert.equal(result[0].records[0], a);
  assert.equal(result[3].records[0], b);
  assert.equal(result[0].report, 'metrics-review.json');
  assert.equal(result[0].methodology, 'method.md');
  assert.equal(result[0].id, buildSummaries([b, a])[0].id);
});

test('conflicting repeated metrics are quarantined; distinct SHA versions stay distinct', () => {
  const a = run(), b = run([sample({metrics: {net: -200, trades: 1}})]);
  assert.equal(buildSummaries([a, b]).length, 0);
  b.params.assessment.extended_metrics_review.sha256 = 'hash-b';
  assert.equal(buildSummaries([a, b]).length, 2);
});

test('malformed cases and numeric strings are rejected, not coerced', () => {
  const cases = [null, sample({metrics: null}), sample({metrics: {net: '-245', trades: 1}}),
    sample({metrics: {net: -245, trades: '1'}}), sample({fee_per_roundtrip: '5'}),
    sample({run_ids: []}), sample({dates: []}), sample({metrics: {net: -245, trades: 1, profit_factor: '0'}}),
    sample({metrics: {net: NaN, trades: 1}}), sample({metrics: {net: -245, trades: 1, closed_trade_drawdown: {maximum: '245'}}})];
  assert.deepEqual(buildSummaries([run(cases)]), []);
});

test('a reconciled single-run case fills absent zero PF, drawdown, and win rate without mutation', () => {
  const original = run(), before = JSON.stringify(original);
  const result = performanceMetrics(original);
  assert.deepEqual(result.metrics, {net: -245, trades: 1, profit_factor: 0, closed_trade_mdd: 245, win_rate: 0});
  assert.equal(result.source.report, 'metrics-review.json');
  assert.equal(JSON.stringify(original), before);
  assert.equal(performanceMetrics(run([sample({metrics: {net: -245 + 1e-9, trades: 1, profit_factor: 0}})])).metrics.profit_factor, 0);
});

test('aggregate RSI evidence never supplies component or zero-trade run metrics', () => {
  const aggregate = sample({candidate: 'rsi', run_ids: ['run-a', 'run-b'], metrics: {net: 800, trades: 6, profit_factor: 2}});
  const component = run([aggregate], {metrics: {net: 800, trades: 6}});
  assert.deepEqual(performanceMetrics(component), {metrics: {net: 800, trades: 6}, source: null});
  const zero = run([sample({metrics: {net: 0, trades: 0, profit_factor: 2}})], {metrics: {net: 0, trades: 0}});
  assert.deepEqual(performanceMetrics(zero), {metrics: {net: 0, trades: 0}, source: null});
});

test('mismatched identity, net, trades, and conflicting report versions cannot fill metrics', () => {
  for (const item of [sample({run_ids: ['other']}), sample({metrics: {net: -244, trades: 1, profit_factor: 0}}),
    sample({metrics: {net: -245, trades: 2, profit_factor: 0}})]) {
    assert.equal(performanceMetrics(run([item])).source, null);
  }
  const conflict = run([sample(), sample({metrics: {net: -245, trades: 1, profit_factor: 0.2}})]);
  assert.equal(performanceMetrics(conflict).source, null);
});

test('no-loss undefined PF and its reason remain distinct from numeric zero', () => {
  const undefinedPF = sample({metrics: {net: 20, trades: 1, profit_factor: null, profit_factor_note: 'undefined when no losing trades'}});
  const source = run([undefinedPF], {metrics: {net: 20, trades: 1}});
  const summary = buildSummaries([source])[0];
  assert.equal(summary.metrics.profit_factor, null);
  assert.equal(summary.metrics.profit_factor_note, 'undefined when no losing trades');
  assert.equal(performanceMetrics(source).metrics.profit_factor, undefined);
  assert.equal(performanceMetrics(source).metrics.profit_factor_note, 'undefined when no losing trades');
  assert.equal(performanceMetrics(run([], {metrics: {net: -245, trades: 1, profit_factor: 0}})).metrics.profit_factor, 0);
  assert.equal(performanceMetrics(run([sample()], {metrics: {net: -245, trades: 1, profit_factor: null}})).metrics.profit_factor, null);
});

test('performance failure stays visible alongside sparse-sample uncertainty', () => {
  const loss = run([], {params: {assessment: {decision: 'performance_fail', research_disposition: 'deferred_sparse_sample', sample_status: 'insufficient_one_unique_trade'}}});
  assert.deepEqual(researchVerdict(loss), {key: 'rejected', label: '관측 구간 손실 · 표본 부족'});
  assert.equal(researchVerdict({...loss, reason: 'date mismatch'}).key, 'blocked');
  assert.equal(researchVerdict(run([])).key, 'unreviewed');
  assert.equal(researchVerdict(run([], {status: 'rejected'})).key, 'unreviewed');
  assert.equal(researchVerdict(run([], {metrics: {net: 0, trades: 0}})).key, 'unreviewed');
  assert.equal(researchVerdict(run([], {params: {assessment: {decision: 'condition_mismatch'}}})).label, '진입 조건 미충족 · 판단 보류');
});
