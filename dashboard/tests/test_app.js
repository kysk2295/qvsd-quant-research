'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function fixture() {
  const base = {worker: 'windows-candidate-research', status: 'completed', symbol: 'NQ', phase: 'recent', updated_at: 1};
  const runs = [];
  for (let candidate = 0; candidate < 12; candidate++) {
    for (const fee of [5, 10]) {
      const id = `candidate-${candidate}-fee-${fee}`;
      const net = candidate === 2 ? 0 : candidate === 0 ? -20 : 20;
      const trades = candidate === 2 ? 0 : 1;
      const item = {candidate: `strategy-${candidate}`, fee_per_roundtrip: fee, dates: ['2026-10-02'], run_ids: [id],
        metrics: {net, trades, sessions: 1, profit_factor: candidate === 0 ? 0 : null, losses: candidate === 0 ? 1 : 0},
        verdict: 'sample_too_sparse_for_adoption'};
      runs.push({...base, id, strategy: item.candidate, metrics: {net, trades}, params: {assessment: {
        extended_metrics_review: {sha256: 'synthetic-report', report: 'synthetic.json', cases: [item, structuredClone(item)]}
      }}});
    }
  }
  runs.push({...base, id: 'deferred-raw-rejected', status: 'rejected', strategy: 'deferred', metrics: {net: 55, trades: 2},
    params: {assessment: {decision: 'deferred', sample_status: 'insufficient_sample'}}});
  runs.push({...base, id: 'observed-failure', strategy: 'failed', metrics: {net: -30, trades: 1},
    params: {assessment: {decision: 'performance_fail', research_disposition: 'deferred_sparse_sample'}}});
  runs.push({...base, id: 'nq-future-import-preparation-test', strategy: 'preparation', phase: 'research_preparation', metrics: {}});
  return {runs, workers: [], events: [], server_time: 100};
}

async function harness() {
  const snapshot = fixture();
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, {
      value: id === 'sort' ? 'updated' : '', checked: false, open: false, innerHTML: '', textContent: '',
      classList: {toggle() {}, add() {}, remove() {}}, addEventListener() {},
      showModal() {this.open = true;}, close() {this.open = false;}
    });
    return elements.get(id);
  };
  const context = vm.createContext({
    document: {getElementById: get, querySelectorAll: () => []},
    fetch: async () => ({ok: true, status: 200, json: async () => structuredClone(snapshot)}),
    setInterval() {}, setTimeout() {}
  });
  vm.runInContext(fs.readFileSync(require.resolve('../static/results.js'), 'utf8'), context);
  vm.runInContext(fs.readFileSync(require.resolve('../static/app.js'), 'utf8'), context);
  // Await the same real refresh pipeline used by the initial page load.
  await vm.runInContext('refresh()', context);
  assert.equal(get('sync').textContent.startsWith('●'), true, get('connection-warning').textContent);
  return {get, context, evaluate: code => vm.runInContext(code, context),
    json: code => JSON.parse(vm.runInContext(`JSON.stringify(${code})`, context))};
}

test('observed-failure filter excludes raw rejected records with a deferred research verdict', async () => {
  const h = await harness();
  h.evaluate("view='performance';filter='rejected';render()");
  assert.deepEqual(h.json('filtered().map(r=>r.id)'), ['observed-failure']);
  assert.equal(h.get('runs').innerHTML.includes('deferred-raw-rejected'), false);
  h.evaluate("filter='deferred';render()");
  assert.deepEqual(h.json('filtered().map(r=>r.id)'), ['deferred-raw-rejected']);
});

test('24 synthetic candidate/cost summaries deduplicate, with 12 rows for the $10 scope', async () => {
  const h = await harness();
  assert.equal(h.evaluate('summaries.length'), 24);
  assert.equal(h.evaluate('filtered().length'), 24);
  assert.equal((h.get('runs').innerHTML.match(/data-id=/g) || []).length, 24);
  h.get('cost').value = '10';
  h.evaluate('render()');
  assert.equal(h.evaluate('filtered().length'), 12);
  assert.deepEqual(h.json('[...new Set(filtered().map(r=>r.fee_per_roundtrip))]'), [10]);
  assert.equal((h.get('runs').innerHTML.match(/data-id=/g) || []).length, 12);
  h.get('cost').value = '5';
  assert.equal(h.evaluate('filtered().length'), 12);
  assert.deepEqual(h.json('[...new Set(filtered().map(r=>r.fee_per_roundtrip))]'), [5]);
});

test('rendered summary and component views distinguish zero PF, undefined PF, and zero trades', async () => {
  const h = await harness();
  assert.equal(h.evaluate("pf(summaries.find(r=>r.candidate==='strategy-0').metrics)"), '0.00');
  assert.equal(h.evaluate("pf(summaries.find(r=>r.candidate==='strategy-1').metrics)"), '계산 불가 · 손실 거래 없음');
  assert.equal(h.evaluate("pf(summaries.find(r=>r.candidate==='strategy-2').metrics)"), '거래 없음');
  assert.equal(h.get('runs').innerHTML.includes('>0.00</td>'), true);
  assert.equal(h.get('runs').innerHTML.includes('계산 불가 · 손실 거래 없음'), true);
  assert.equal(h.get('runs').innerHTML.includes('거래 없음'), true);
  const before = h.json("state.runs.find(r=>r.id==='candidate-2-fee-10').metrics");
  h.evaluate("view='performance';render()");
  assert.deepEqual(h.json("metrics(state.runs.find(r=>r.id==='candidate-2-fee-10'))"), {net: 0, trades: 0});
  assert.deepEqual(h.json("state.runs.find(r=>r.id==='candidate-2-fee-10').metrics"), before);
  assert.deepEqual(h.json("state.runs.find(r=>r.id==='candidate-0-fee-10').metrics"), {net: -20, trades: 1});
});

test('preparation is visible only in the research view and carries no performance KPIs', async () => {
  const h = await harness();
  h.evaluate("view='performance';render()");
  assert.equal(h.evaluate("filtered().some(r=>r.id==='nq-future-import-preparation-test')"), false);
  h.evaluate("view='research';render()");
  assert.deepEqual(h.json('filtered().map(r=>r.id)'), ['nq-future-import-preparation-test']);
  assert.equal(h.get('runs').innerHTML.includes('평가 대상 아님'), true);
  assert.equal(h.get('runs').innerHTML.includes('작업 완료 · 성과 평가 아님'), true);
  h.evaluate("detail('nq-future-import-preparation-test')");
  assert.equal(h.get('detail-body').innerHTML.includes('순손익과 PF 평가 대상이 아닙니다'), true);
  assert.equal(h.get('detail-body').innerHTML.includes('detail-kpis'), false);
});
