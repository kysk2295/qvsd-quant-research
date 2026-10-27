(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.DashboardResults = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = value => typeof value === 'string' && value.trim().length > 0;
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const assessment = run => object(run?.params?.assessment) ? run.params.assessment : {};
  const researchPhases = new Set(['research_preparation', 'data_quality', 'data_analysis', 'hypothesis_research', 'data-audit']);

  function recordKind(run) {
    if (researchPhases.has(run?.phase)) return 'research';
    const empty = !object(run?.metrics) || Object.keys(run.metrics).length === 0;
    if (empty && /^nq-/.test(run?.id || '') && /preparation|readiness|data-audit|research-status/.test(run.id)) return 'research';
    return 'performance';
  }

  function canonical(value) {
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    if (object(value)) return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
    return JSON.stringify(value);
  }

  function stableId(identity) {
    let a = 2166136261, b = 3339675911;
    for (let i = 0; i < identity.length; i++) {
      a = Math.imul(a ^ identity.charCodeAt(i), 16777619);
      b = Math.imul(b ^ identity.charCodeAt(i), 2246822519);
    }
    return 'summary-' + (a >>> 0).toString(16).padStart(8, '0') + (b >>> 0).toString(16).padStart(8, '0');
  }

  function stringList(value) {
    return Array.isArray(value) && value.length > 0 && value.every(text) && new Set(value).size === value.length;
  }

  function validCase(item) {
    if (!object(item) || !text(item.candidate) || !finite(item.fee_per_roundtrip) || item.fee_per_roundtrip < 0) return false;
    if (!stringList(item.run_ids) || !stringList(item.dates) || !item.dates.every(date => /^\d{4}-\d{2}-\d{2}$/.test(date))) return false;
    const metrics = item.metrics;
    if (!object(metrics) || !finite(metrics.net) || !Number.isInteger(metrics.trades) || metrics.trades < 0) return false;
    for (const key of ['profit_factor', 'closed_trade_mdd', 'win_rate']) {
      if (metrics[key] !== undefined && metrics[key] !== null && !finite(metrics[key])) return false;
    }
    if (finite(metrics.profit_factor) && metrics.profit_factor < 0) return false;
    if (metrics.closed_trade_drawdown !== undefined && metrics.closed_trade_drawdown !== null) {
      if (!object(metrics.closed_trade_drawdown) || !finite(metrics.closed_trade_drawdown.maximum) || metrics.closed_trade_drawdown.maximum < 0) return false;
    }
    return true;
  }

  function buildSummaries(runs) {
    if (!Array.isArray(runs)) return [];
    const groups = new Map(), records = new Map();
    for (const run of runs) if (text(run?.id) && !records.has(run.id)) records.set(run.id, run);
    for (const run of runs) {
      const review = assessment(run).extended_metrics_review;
      if (!object(review) || !text(review.sha256) || !text(review.report) || !Array.isArray(review.cases)) continue;
      for (const item of review.cases) {
        if (!validCase(item)) continue;
        const identity = canonical([review.sha256, item.candidate, item.fee_per_roundtrip, [...item.run_ids].sort(), [...item.dates].sort()]);
        const fingerprint = canonical({metrics: item.metrics, verdict: item.verdict});
        const prior = groups.get(identity);
        if (prior) {
          // Conflicting copies cannot be resolved by array order. Quarantine them.
          if (prior.fingerprint !== fingerprint) prior.conflict = true;
          continue;
        }
        groups.set(identity, {fingerprint, conflict: false, summary: {
          ...item,
          id: stableId(identity),
          report: review.report,
          sha256: review.sha256,
          methodology: review.methodology,
          records: item.run_ids.map(id => records.get(id)).filter(Boolean)
        }});
      }
    }
    return [...groups.values()].filter(group => !group.conflict).map(group => group.summary);
  }

  function performanceMetrics(run) {
    const metrics = object(run?.metrics) ? {...run.metrics} : {};
    if (!finite(metrics.net) || !Number.isInteger(metrics.trades) || metrics.trades <= 0) return {metrics, source: null};
    const candidates = buildSummaries([run]).filter(item => item.run_ids.length === 1 && item.run_ids[0] === run.id &&
      item.metrics.trades === metrics.trades && Math.abs(item.metrics.net - metrics.net) <= 1e-8);
    if (!candidates.length) return {metrics, source: null};
    const additions = item => ({
      profit_factor: item.metrics.profit_factor,
      closed_trade_mdd: item.metrics.closed_trade_mdd ?? item.metrics.closed_trade_drawdown?.maximum,
      win_rate: item.metrics.win_rate,
      profit_factor_note: item.metrics.profit_factor_note
    });
    const values = additions(candidates[0]);
    // Different report versions must agree before supplying any absent metric.
    if (candidates.some(item => canonical(additions(item)) !== canonical(values))) return {metrics, source: null};
    let changed = false;
    for (const key of Object.keys(values)) {
      if (metrics[key] === undefined && finite(values[key])) {
        metrics[key] = values[key];
        changed = true;
      }
    }
    if (!finite(metrics.profit_factor) && metrics.profit_factor_note === undefined && text(values.profit_factor_note)) {
      metrics.profit_factor_note = values.profit_factor_note;
      changed = true;
    }
    const item = candidates[0];
    return {metrics, source: changed ? {
      report: item.report, sha256: item.sha256, methodology: item.methodology,
      candidate: item.candidate, run_ids: [...item.run_ids]
    } : null};
  }

  function researchVerdict(run) {
    const a = assessment(run);
    if (/date mismatch|coverage mismatch|기간.*탈락|봉 범위 불일치|범위.*확인 불가/i.test((run?.reason || '') + ' ' + (run?.phase || ''))) {
      return {key: 'blocked', label: '데이터 오류 · 비교 제외'};
    }
    if (recordKind(run) === 'research') return {key: 'research', label: run?.status === 'completed' ? '작업 완료 · 성과 평가 아님' : '연구 작업 · 성과 평가 아님'};
    const context = [a.decision, a.research_disposition, a.sample_status].filter(text).join(' ');
    const sparse = /insufficient|sparse/.test(context);
    if (a.decision === 'performance_fail' || a.research_disposition === 'performance_fail') {
      const label = finite(run?.metrics?.net) && run.metrics.net < 0 ? '관측 구간 손실' : '관측 구간 기준 미달';
      return {key: 'rejected', label: label + (sparse ? ' · 표본 부족' : /deferred/.test(context) ? ' · 추가 검증' : '')};
    }
    if (/condition_mismatch/.test(context)) return {key: 'deferred', label: '진입 조건 미충족 · 판단 보류'};
    if (sparse) return {key: 'deferred', label: '표본 부족 · 판단 보류'};
    if (/deferred/.test(context)) return {key: 'deferred', label: '판단 보류 · 추가 검증'};
    if (run?.status === 'rejected') return {key: 'unreviewed', label: '판정 재확인 필요'};
    return {key: 'unreviewed', label: '채택 여부 미확인'};
  }

  return {recordKind, buildSummaries, researchVerdict, performanceMetrics};
});
