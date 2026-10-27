'use strict';
let state={runs:[],workers:[],events:[]}, summaries=[], metricCache=new Map(), filter='all', view='summary', selected=null, detailHTML='';
const $=id=>document.getElementById(id), model=DashboardResults;
const names={breakout:'OR 돌파',retest:'OR 리테스트',failed_ib:'IB 실패돌파',bollinger:'Bollinger',macd:'MACD',nr7:'NR7',channel:'Channel',gap:'Gap','moving-momentum':'Moving Momentum','cafe-ib60':'Cafe IB60','cafe-retest15':'Cafe Retest15','cafe-retest30':'Cafe Retest30','bollinger-return':'Bollinger',stochastic:'Stochastic','macd-cross':'MACD',ofi:'OFI',rsi2:'RSI2'};
const labels={queued:'대기',running:'진행 중',completed:'계산 완료',failed:'오류',rejected:'계산 완료',blocked:'확인 필요'};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(v,d=0)=>Number.isFinite(v)?v.toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:d}):'미보고';
const money=v=>Number.isFinite(v)?`${v<0?'−':v>0?'+':''}$${num(Math.abs(v),Number.isInteger(v)?0:2)}`:'미보고';
const ago=t=>{if(!Number.isFinite(t))return '미보고';const s=Math.max(0,Math.floor(Date.now()/1000-t));return s<60?`${s}초 전`:s<3600?`${Math.floor(s/60)}분 전`:s<86400?`${Math.floor(s/3600)}시간 전`:`${Math.floor(s/86400)}일 전`;};
const clock=t=>new Date(t*1000).toLocaleTimeString('ko-KR',{hour12:false});
const isSummary=r=>Array.isArray(r.run_ids)&&typeof r.candidate==='string';
const title=r=>names[r.candidate||r.strategy]||r.candidate||r.strategy;
const archived=r=>!['windows-experiment-runner','windows-candidate-research'].includes(r.worker)||/Superseded/i.test(r.phase||'');
const invalid=r=>/date mismatch|coverage mismatch|기간.*탈락|봉 범위 불일치|범위.*확인 불가/i.test((r.reason||'')+' '+(r.phase||''));
const effective=r=>r.status==='running'&&!state.workers.some(w=>w.id===r.worker&&w.online)?'stale':r.status;
const metrics=r=>isSummary(r)?r.metrics:metricCache.get(r.id)?.metrics||r.metrics||{};
const drawdown=m=>m.closed_trade_mdd??m.closed_trade_drawdown?.maximum;
const period=r=>{const dates=[...r.dates].sort();return `${dates[0]} ~ ${dates.at(-1)}`;};
function pf(m){
 if(Number.isFinite(m.profit_factor))return num(m.profit_factor,2);
 if(m.trades===0)return '거래 없음';
 if(m.losses===0||/no losing trades/.test(m.profit_factor_note||''))return '계산 불가 · 손실 거래 없음';
 return '미보고';
}
function verdict(r){
 if(!isSummary(r))return model.researchVerdict(r);
 if(r.verdict==='negative_after_cost_in_tested_variant')return {key:'rejected',label:'관측 구간 손실'};
 if(r.verdict==='sample_too_sparse_for_adoption')return {key:'deferred',label:(r.metrics.net<0?'관측 구간 손실 · ':'')+'표본 부족'};
 if(r.verdict==='positive_but_cost_or_concentration_fragile')return {key:'deferred',label:'양수 · 비용/수익 집중에 취약'};
 return {key:'unreviewed',label:'채택 여부 미확인'};
}
function badge(r){
 const v=verdict(r),assessment=`<span class="badge ${v.key==='deferred'?'blocked':v.key}">${esc(v.label)}</span>`;
 if(isSummary(r))return assessment;
 const s=effective(r);
 return `<span class="badge ${esc(s)}">${s==='stale'?'응답 없음':model.recordKind(r)==='research'&&s==='completed'?'작업 완료':esc(labels[s]||s)}</span> `+assessment+(s==='running'?`<progress class="progress" value="${Number(r.progress)||0}" max="100" aria-label="실험 진행률"></progress>`:'');
}
function stage(r){
 if(isSummary(r))return '저장 원장 합산';
 if(model.recordKind(r)==='research')return '준비 · 데이터 점검';
 if(r.params?.assessment?.native_fill_cost_limitation||r.params?.native_trade_ledger)return 'NinjaTrader 백테스트';
 return r.params?.engine==='nt'?'NT 기능 확인':r.params?.engine==='python'?'가격 대리 탐색':r.source||'미분류';
}
function limitation(r){
 if(isSummary(r))return `${num(r.metrics.sessions)}세션 · 독립 OOS 아님 · ${r.run_ids.length}개 실행 합산`;
 if(invalid(r))return '요청 기간과 적재 기간 불일치 · 성과 비교 제외';
 return r.reason||(r.params?.engine==='python'?'이미 본 데이터 · 독립 OOS 아님':'검증 판정 미보고');
}
function filtered(){
 const q=$('search').value.toLowerCase(),symbol=$('symbol').value,cost=$('cost').value;
 const base=view==='summary'?summaries:state.runs.filter(r=>model.recordKind(r)===(view==='research'?'research':'performance'));
 const rows=base.filter(r=>{
  if(!$('archive').checked&&(isSummary(r)?!r.records.some(x=>!archived(x)):archived(r)))return false;
  if(symbol&&(isSummary(r)?!r.records.some(x=>x.symbol===symbol):r.symbol!==symbol))return false;
  if(view==='summary'&&cost&&r.fee_per_roundtrip!==Number(cost))return false;
  if(!JSON.stringify([title(r),r.dataset,r.dates,r.source]).toLowerCase().includes(q))return false;
  if(filter==='all')return true;
  if(['deferred','rejected'].includes(filter))return verdict(r).key===filter;
  if(filter==='blocked')return verdict(r).key===filter||(!isSummary(r)&&r.status==='blocked');
  if(filter==='completed')return isSummary(r)||['completed','rejected'].includes(r.status);
  return !isSummary(r)&&effective(r)===filter;
 });
 const sort=$('sort').value;
 return rows.sort((a,b)=>sort==='net'?(metrics(b).net??-Infinity)-(metrics(a).net??-Infinity):sort==='dd'?(drawdown(metrics(a))??Infinity)-(drawdown(metrics(b))??Infinity):view==='summary'?title(a).localeCompare(title(b))||b.fee_per_roundtrip-a.fee_per_roundtrip:b.updated_at-a.updated_at);
}
function render(){
 const current=state.runs.filter(r=>!archived(r)),calculated=current.filter(r=>Number.isFinite(r.metrics?.trades));
 const worker=state.workers.find(w=>w.id==='windows-experiment-runner'),active=current.filter(r=>effective(r)==='running').length,queued=current.filter(r=>r.status==='queued').length;
 $('research-status').innerHTML=`<div class="status-line"><strong>저장된 전략 ${new Set(summaries.map(r=>r.candidate)).size}종 · 비용별 합산 ${summaries.length}건</strong><span>${!worker?.online?'실행기 연결 확인 필요':active?`${active}건 실행 중`:queued?`${queued}건 대기`:'실행기 대기'} · 개별 계산 ${calculated.length}건</span></div><p class="status-explanation">기존 거래 기록에서 계산한 성과입니다. 기간과 비용을 함께 확인해 주세요. 모든 합산은 이미 관측한 개발 자료이며, 전략 채택이나 독립 검증 통과를 뜻하지 않습니다.</p>`;
 $('workers').innerHTML=state.workers.length?state.workers.map(w=>`<div class="worker"><div><div class="worker-title">${esc(w.label||w.id)}</div><small>${esc(w.message||w.phase||'상태 대기')} · 마지막 응답 ${ago(w.updated_at)}</small></div><span class="badge ${w.online?'online':'stale'}">${w.online?'● 연결됨':'○ 연결 끊김'}</span></div>`).join(''):'<div class="empty">연결된 작업자가 없습니다. 저장된 결과는 조회할 수 있습니다.</div>';
 const rows=filtered();$('filtered-count').textContent=rows.length;
 $('cost').classList.toggle('hidden',view!=='summary');
 $('view-description').textContent=view==='summary'?'후보·비용·관측 기간별 합산 성과입니다. 동일한 보고서의 중복 사본은 한 번만 표시합니다.':view==='research'?'수집·품질·준비 기록입니다. 이 작업들은 전략 손익을 계산하지 않습니다.':'개별 실행의 성과입니다. 합산 PF를 구성 실행에 나누어 붙이지 않습니다.';
 $('runs').innerHTML=rows.length?rows.map(r=>{
  const m=metrics(r),research=model.recordKind(r)==='research',excluded=!isSummary(r)&&invalid(r),noMetric=research?'평가 대상 아님':excluded?'비교 제외':null;
  return `<tr tabindex="0" data-id="${esc(r.id)}" aria-label="${esc(title(r))} 상세"><td><span class="strategy">${esc(title(r))}</span><span class="dataset">${isSummary(r)?`${period(r)}<br>왕복 수수료 $${num(r.fee_per_roundtrip)} · ${num(m.sessions)}세션`:`${esc(r.dataset)} · ${esc(r.cost||r.source)}`}</span></td><td>${esc(stage(r))}</td><td>${badge(r)}</td><td class="${noMetric||!Number.isFinite(m.net)?'':m.net<0?'negative':'positive'}">${noMetric||money(m.net)}</td><td>${noMetric||pf(m)}</td><td>${noMetric||(Number.isFinite(drawdown(m))?'$'+num(drawdown(m),2):'미보고')}</td><td>${research?'평가 대상 아님':num(m.trades)}</td><td class="reason-cell">${esc(limitation(r))}</td></tr>`;
 }).join(''):'<tr><td colspan="8" class="empty">조건에 맞는 기록이 없습니다.</td></tr>';
 $('events').innerHTML=state.events.length?state.events.map(e=>`<div class="event"><time>${clock(e.created)}</time><span>${esc(e.message)}</span></div>`).join(''):'<div class="empty">운영 로그가 없습니다.</div>';
 if(selected&&$('detail').open)detail(selected,false);
}
function kpis(m){return `<div class="detail-kpis"><div>순손익<strong>${money(m.net)}</strong></div><div>PF · 총이익 ÷ 총손실 절댓값<strong>${pf(m)}</strong></div><div>청산 거래 기준 최대낙폭<strong>${Number.isFinite(drawdown(m))?'$'+num(drawdown(m),2):'미보고'}</strong></div><div>거래 수<strong>${num(m.trades)}</strong></div></div>`;}
function summaryDetail(r){
 const m=r.metrics;
 return `${badge(r)}<p class="notice">이 합산은 아래 실행 ID와 기간에만 해당합니다. 청산 기준 낙폭은 미실현 손익을 포함한 계좌 손실 한도가 아닙니다.</p>${kpis(m)}<dl class="detail-meta"><dt>관측 기간</dt><dd>${period(r)} · ${num(m.sessions)}세션 / 거래 발생 ${num(m.active_sessions)}세션</dd><dt>비용 가정</dt><dd>왕복 수수료 $${num(r.fee_per_roundtrip)}. 원장에 반영된 체결 가격을 사용합니다.</dd><dt>승률 / 손익비</dt><dd>${Number.isFinite(m.win_rate)?num(m.win_rate*100,1)+'%':'미보고'} / ${num(m.realized_payoff_ratio,2)}</dd><dt>거래당 기대손익</dt><dd>${money(m.expectancy_per_trade)}</dd><dt>최고 수익일 제외</dt><dd>${money(m.net_without_best_positive_day)}</dd><dt>검증 성격</dt><dd>이미 관측한 개발 자료 · 독립 OOS 아님 · 채택 미확정</dd><dt>합산 보고서</dt><dd>${esc(r.report)}</dd><dt>계산 방법</dt><dd>${esc(r.methodology||'미보고')}</dd><dt>보고서 SHA256</dt><dd>${esc(r.sha256)}</dd><dt>구성 실행 ID</dt><dd>${r.run_ids.map(esc).join('<br>')}</dd></dl><h2>추가 체결 비용 민감도</h2><p class="subtle">기존 체결마다 불리한 비용을 더한 산술 검사입니다. 새 체결 경로 검증이 아닙니다.</p><div class="cost-grid">${(m.additional_cost_sensitivity||[]).map(c=>`<div>체결당 +${num(c.ticks_per_fill)}틱<strong>${money(c.net)}</strong></div>`).join('')}</div><details><summary>일별 손익</summary><pre>${esc(JSON.stringify(m.daily||{},null,2))}</pre></details><details><summary>저장된 전체 합산 지표</summary><pre>${esc(JSON.stringify(m,null,2))}</pre></details>`;
}
function detail(id,open=true){
 const r=summaries.find(x=>x.id===id)||state.runs.find(x=>x.id===id);if(!r)return;
 selected=id;$('detail-title').textContent=`${title(r)} · ${isSummary(r)?`왕복 $${r.fee_per_roundtrip} 합산`:r.symbol}`;
 let content;
 if(isSummary(r))content=summaryDetail(r);
 else{
  const m=metrics(r),source=metricCache.get(r.id)?.source,related=summaries.filter(s=>s.run_ids.includes(r.id)),research=model.recordKind(r)==='research';
  content=`${badge(r)}<p class="notice">${esc(limitation(r))}${invalid(r)?' · 아래는 진단용 원본 수치이며 유효한 기간 성과가 아닙니다.':''}</p>${research?'<p>준비·데이터 점검 작업으로 순손익과 PF 평가 대상이 아닙니다.</p>':kpis(m)}${source?`<p class="subtle">누락 지표 보완: ${esc(source.report)}. 이 실행 하나만 포함하고 순손익·거래 수가 일치하는 보고서입니다.</p>`:''}${related.length?`<h2>이 실행이 포함된 전략별 합산</h2><div class="related">${related.map(s=>`<button class="secondary" data-detail="${esc(s.id)}">${esc(title(s))} · 왕복 $${num(s.fee_per_roundtrip)} · ${period(s)}</button>`).join('')}</div>`:''}<dl class="detail-meta"><dt>데이터</dt><dd>${esc(r.dataset)}</dd><dt>현재 단계</dt><dd>${esc(r.phase||'미보고')} · ${num(r.progress)}%</dd><dt>다음 검증</dt><dd>${esc(r.params?.assessment?.next_action||'미보고')}</dd><dt>근거</dt><dd>${esc(r.evidence||'미보고')}</dd><dt>작업자</dt><dd>${esc(r.worker)}</dd><dt>코드 버전</dt><dd>${esc(r.code_commit||'미기록')}</dd><dt>실행 ID</dt><dd>${esc(r.id)}</dd></dl>${equityChart(r)}<details><summary>실험 설정 원본</summary><pre>${esc(JSON.stringify(r.params||{},null,2))}</pre></details><details><summary>성과 지표 원본</summary><pre>${esc(JSON.stringify(r.metrics||{},null,2))}</pre></details>`;
 }
 if(content!==detailHTML){$('detail-body').innerHTML=content;detailHTML=content;}
 if(open&&!$('detail').open)$('detail').showModal();
}
function equityChart(r){
 const curve=r.equity||[];if(curve.length<2)return '';
 const vals=curve.map(p=>p.value),lo=Math.min(...vals),hi=Math.max(...vals),range=hi-lo||1,pts=vals.map((v,i)=>`${12+i/(vals.length-1)*696},${160-(v-lo)/range*135}`).join(' ');
 return `<h2>보고된 계좌 곡선</h2><svg class="chart" viewBox="0 0 720 180" role="img" aria-label="보고된 계좌 곡선"><polyline points="${pts}" fill="none" stroke="#11856d" stroke-width="2.5"/></svg><div class="chart-label"><span>${esc(curve[0].date)}</span><span>최저 $${num(lo)} / 최고 $${num(hi)}</span><span>${esc(curve.at(-1).date)}</span></div>`;
}
async function refresh(){
 try{
  const res=await fetch('/api/state',{cache:'no-store'});if(res.status===401){location.href='/';return;}if(!res.ok)throw Error('HTTP '+res.status);
  state=await res.json();summaries=model.buildSummaries(state.runs);metricCache=new Map(state.runs.map(r=>[r.id,model.performanceMetrics(r)]));
  $('sync').textContent='● 3초마다 갱신 · '+clock(state.server_time);$('connection-warning').classList.add('hidden');render();
 }catch(e){$('sync').textContent='○ 갱신 실패';$('connection-warning').textContent='최신 상태를 불러오지 못했습니다. 아래는 마지막으로 받은 기록입니다. 자동 재연결을 시도합니다.';$('connection-warning').classList.remove('hidden');}
}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;filter='all';document.querySelectorAll('[data-view]').forEach(t=>{t.classList.toggle('selected',t===b);t.setAttribute('aria-pressed',String(t===b));});document.querySelectorAll('[data-filter]').forEach(t=>t.classList.toggle('selected',t.dataset.filter==='all'));render();});
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(t=>t.classList.toggle('selected',t===b));render();});
['search','symbol','sort','archive','cost'].forEach(id=>$(id).addEventListener('input',render));
$('runs').onclick=e=>{const tr=e.target.closest('[data-id]');if(tr)detail(tr.dataset.id);};
$('runs').onkeydown=e=>{if(e.key==='Enter'){const tr=e.target.closest('[data-id]');if(tr)detail(tr.dataset.id);}};
$('detail-body').onclick=e=>{const b=e.target.closest('[data-detail]');if(b)detail(b.dataset.detail);};
$('close-detail').onclick=()=>{$('detail').close();selected=null;};
$('export').onclick=()=>{
 const cell=v=>'"'+String(v??'').replace(/^[=+@\-]/,"'$&").replace(/"/g,'""')+'"';
 const rows=[['id','strategy','scope','dataset','cost','verdict','net','profit_factor','pf_note','closed_trade_mdd','trades','run_ids','report_sha256'],...filtered().map(r=>{const m=metrics(r);return [r.id,title(r),view,isSummary(r)?period(r):r.dataset,isSummary(r)?r.fee_per_roundtrip:r.cost,verdict(r).label,m.net,m.profit_factor,Number.isFinite(m.profit_factor)?'':pf(m),drawdown(m),m.trades,isSummary(r)?r.run_ids.join(';'):r.id,isSummary(r)?r.sha256:metricCache.get(r.id)?.source?.sha256];})];
 const url=URL.createObjectURL(new Blob(['\uFEFF'+rows.map(r=>r.map(cell).join(',')).join('\n')],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=`quant-lab-${view}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
refresh();setInterval(refresh,3000);
