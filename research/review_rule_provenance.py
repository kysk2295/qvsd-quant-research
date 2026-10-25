"""Source/code specification audit. No market data read, PnL computation or execution."""
import json
import subprocess
from datetime import datetime,timezone
from runner.core import ROOT,atomic,file_hash

def main():
    chart='https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/'
    tv='https://www.tradingview.com/support/solutions/'
    rows=[
      dict(id='rsi-pullback-v1',strategies=['CodexRsiPullback'],code=['native/CodexRsiPullback.cs'],manifest='research/rsi-pullback-manifest.json',
        source=chart+'rsi-2',source_status='Publisher educational exposition verified; Connors original book/testing not independently reproduced',
        original=dict(entry='Daily close relative to SMA200; RSI2 oversold long/overbought short, threshold variants discussed',stop='Connors exposition does not advocate stops; alternatives discussed',exit='SMA5 crossing; optional trailing alternatives',reentry='Not exhaustively specified',bars='Daily examples',session='No NQ RTH prescription',maximum_entries='No four/day cap stated'),
        implemented=dict(entry='Long only Close>SMA200 and RSI(2,1)<selected2or5; market after closed five-minute signal',stop='48 ticks from fill',exit='Close>SMA5 or10 five-minute bars from fill or15:55ET',reentry='Allowed when flat, not pending and caps allow; entries counter increments at order submission',bars='5minute ETH indicator history; minimum200 bars',session='RTH09:30–16:00; eligible bar starts09:40<=start<15:30, bar-end decisions09:45–15:30',maximum_entries='4/day; realized after$10fee<=-900 entry halt'),
        validity='Functional test of a long-only intraday adaptation, not replication of daily Connors RSI2. Stop, timeframe and cap effects unisolated.'),
      dict(id='bollinger-return-v1',strategies=['CodexBollingerReturn','CodexBollingerClock'],code=['native/CodexBollingerReturn.cs','native/CodexBollingerClock.cs'],manifest='research/bollinger-return-manifest.json',
        source=tv+'43000599826-bollinger-bands-strategy-directed/',source_status='Publisher Pine code verified; adjacent prose describes opposite crossing direction, code chosen explicitly',
        original=dict(entry='Pine lower-band upward crossing long; upper-band downward crossing short; band-price stop-entry orders with OCA cancellation',stop='Entry stop order is not a protective stop-loss; no48tick protective exit in sample',exit='Opposite entries can reverse; no SMA/time exit shown',reentry='Entry cancellation/reversal semantics; no flat-only gate in sample',bars='Chart-selected series, length20/deviation2',session='No RTH reset specified',maximum_entries='No four/day cap in sample'),
        implemented=dict(entry='Same band crossing formulas; market only while flat; population sigma20',stop='48tick protective stop from fill',exit='Current SMA20 reached or10 one-minute bars after fill or15:55ET',reentry='Later qualifying crossing while flat; occupied-bar opposite signal not reversed',bars='1minute; bands reset daily,21RTHbars before entry',session='09:51–15:25ET entries',maximum_entries='4 submitted entries/day; realized after$10fee<=-900 entry halt'),
        validity='Material execution/exit/exposure changes. Frozen future plan tests this specific standalone NQ variant, not TradingView strategy replication or all-day Bollinger edge.'),
      dict(id='nr7-rth-v1',strategies=['CodexNr7Rth','CodexNr7RthExtension'],code=['native/CodexNr7Rth.cs','native/CodexNr7RthExtension.cs'],manifest='research/nr7-rth-manifest.json',
        source=chart+'narrow-range-day-nr7',source_status='ChartSchool interpretation verified; Crabel original book unverified',
        original=dict(entry='ChartSchool prior narrow-day high/low breakout; distinguishes Crabel opening-range entry',stop='Opposite NR extreme invalidation and ATR/SAR alternatives discussed; no single mandatory48tick stop',exit='First-day/first-profitable-close and other alternatives discussed',reentry='No exhaustive rule',bars='Seven daily high-low ranges',session='NQ RTH-only daily construction not specified',maximum_entries='No one/day or four/day requirement stated'),
        implemented=dict(entry='Prior completed RTH range strictly below each six predecessors; minute close beyond prior high/low by one tick',stop='48 ticks',exit='15:55ET session liquidation or protective stop',reentry='None after first submission that day',bars='1minute execution;390minute completed RTH daily context',session='09:31–15:25ET entries',maximum_entries='1/day, not4; one-contract exposure'),
        validity='One-trade sparse result only applies to this RTH/close-confirmed/fixed-stop variant; cannot reject original NR7 or Crabel strategy.'),
      dict(id='cafe-positive-data-extension',strategies=['CodexCafeRange'],code=['native/CodexCafeRange.cs'],manifest='research/cafe-extension-manifest.json',
        source='https://cafe.naver.com/f-e/cafes/31685329/articles/42',source_status='Direct fetch inaccessible; repository summaries of articles5,10,17,33,42 available, not full original execution specification',
        original=dict(entry='OR breakout/retest and IB return concepts in repository notes',stop='Exact original numeric protective rules unverified',exit='Exact original target and time rules unverified',reentry='Article33 discusses additional entries; exact counted-entry semantics unverified',bars='Exact complete trading specification unavailable',session='Article42 summary says08:30–09:00 IB, timezone unverified',maximum_entries='Original maximum unverified'),
        implemented=dict(entry='OR15/30 breakout or six-bar retest with VWAP filters; failedIB uses60minute range return',stop='Breakout max(1.5 rollingTR14, quarter range); retest beyond low/high and buffer; failedIB beyond excursion; NOT fixed48ticks',exit='2R target for breakout/retest; IBmidpoint for failedIB;15:55ET liquidation',reentry='Flat-only, repeated setups/re-arming allowed; no pyramiding',bars='5minute; rollingTR14, RTH VWAP',session='09:30RTH range start; eligible bar start<14:55ET',maximum_entries='4 submissions/day; gross realized -900 halt; entry risk(distance+2points)*20+10<=300 else reject'),
        validity='Research interpretation, not verified exact cafe replication. Budget filter changes eligible setups; original rejected-setup counterfactual PnL unmeasured.'),
      dict(id='macd-cross-v1',strategies=['CodexMacdCross'],code=['native/CodexMacdCross.cs'],manifest='research/macd-cross-manifest.json',
        source=tv+'43000644943-macd-strategy/',source_status='Publisher strategy description verified',
        original=dict(entry='Histogram negative-to-positive long, positive-to-negative switches short;12/26/9 EMA defaults',stop='No48tick protective stop specified',exit='Opposite sign switches direction',reentry='Direction switch described, not flat-only gating',bars='Chart-selected series',session='No RTH reset prescribed',maximum_entries='No four/day cap stated'),
        implemented=dict(entry='Histogram sign crossing; flat-only, no same-bar reversal',stop='48 ticks',exit='Opposite histogram sign or10bars or15:55ET',reentry='Needs a later new crossing after flat',bars='1minute; daily reset, fast/slow seeded first close;80bar warmup',session='10:50–15:25ET entries',maximum_entries='4/day; realized after$10fee<=-900 halt'),
        validity='Negative result is restricted to this finite-hold intraday variant; original reversal policy not tested.'),
      dict(id='stochastic-fast-v1',strategies=['CodexStochasticFast'],code=['native/CodexStochasticFast.cs'],manifest='research/stochastic-manifest.json',
        source='https://docs.algotest.in/signals/pinescripts/stochastic_oscillator_strategy/',source_status='Publisher demo Pine verified, not Lane original research',
        original=dict(entry='RawK14 crossing SMA3(K), currentK<20 for long or>80 for short',stop='50 price points from position average',exit='100point target; opposite entry may reverse',reentry='Reversal-capable entry statements; no flat-only filter',bars='Chart-selected series',session='No NQ RTH reset',maximum_entries='No four/day cap stated'),
        implemented=dict(entry='Same raw14/3 and20/80 conditions, flat-only',stop='48ticks=12points',exit='96ticks=24points target;20bars or15:55ET',reentry='Later qualifying crossing after flat; no occupied-bar reversal',bars='1minute RTH-reset; zero-width invalidates K/D history',session='09:50–15:25ET entries',maximum_entries='4/day; realized after$10fee<=-900 halt'),
        validity='50point original stop costs$1000 for1NQ before costs: incompatible with$300 assumption. 48tick substitution changes strategy, cannot establish original failure.')
    ]
    for row in rows:
        row['files_sha256']={p:file_hash(ROOT/p) for p in row['code']+[row['manifest']]}
        anchors=[]
        for p in row['code']:
            for n,line in enumerate((ROOT/p).read_text().splitlines(),1):
                if any(s in line for s in ('entries>=','SetStopLoss','SetProfitTarget','m<','m>=','new TimeSpan(15','risk>300','realized<=','pending ||','Position.MarketPosition')):
                    anchors.append(dict(file=p,line=n,text=line.strip()))
        row['code_anchors']=anchors
    immutable=json.loads((ROOT/'research/equity-audit-immutable-inputs.json').read_text())
    assert all(file_hash(ROOT/p)==h for p,h in immutable.items())
    history=[]
    for commit,path,needle in [('1f6cd9e','research/backtest.py','n>=4'),('85e1116','native/CodexRsiPullback.cs','12-point')]:
        body=subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT,text=True)
        history.append(dict(commit=commit,path=path,matches=[dict(line=n,text=t.strip()) for n,t in enumerate(body.splitlines(),1) if needle in t]))
    report=dict(reviewed_at_utc=datetime.now(timezone.utc).isoformat(),candidates=rows,history=history,
        conclusion='Implementation checks are not source-strategy validity or justification of shared constraints. Previous performance decisions apply only to exact tested NQ adaptations.',
        max_four='Present in initial proxy1f6cd9e; no supporting cap comparison identified. Native code usually counts submissions, not necessarily filled/competition-counted trades.',
        stop48='RSI85e1116 budget estimate:12points*20+2points*20+10=290. This is a research policy, not original optimum or guaranteed maximum loss.',
        competition=dict(source='https://cafe.naver.com/f-e/cafes/31685329/articles/55',status='Direct current fetch inaccessible; repository report says minimum4 per round, not maximum4 per day',evidence='research/build_report.py',cause_of_confusion='Unknown; do not infer causal origin merely because both numbers equal4',deadline='Repository reports Oct29 18:00; current original notice/timezone not reverified. Nov7 research decision cannot be represented as meeting it.'),
        risk_policy='Define strategy-specific invalidation/exit first, then position risk. If1NQ exceeds unchanged$300assumption, record infeasible; no forced48tick shrink, risk expansion, or unsolicited MNQ substitution. No protective-stop original requires separate risk specification before execution.',
        material_design_issue='Max4 censors later opportunities;48tick and time exits change payoff and reversal mechanics. Their appropriateness is unvalidated. Existing numerical audit remains valid for the constrained implementation only.',
        prospective_interpretation='Keep exact frozen Bollinger plan/source/cost/dates/selection. It tests only standalone constrained NQ variant; no original replication claim. If redesign desired, separate preregistration and new future dates needed; current native budget0.',
        immutable_input_hashes=immutable,source_code_hashes={p:file_hash(ROOT/p) for row in rows for p in row['code']},
        native_runs=0,downloads=0,pnl_recomputed=False)
    atomic(ROOT/'research/strategy-rule-provenance-review.json',report)
    print(json.dumps(dict(candidates=len(rows),native_runs=0,downloads=0,immutable_hashes_preserved=True)))

if __name__=='__main__':main()
