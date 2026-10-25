# Strategy Analyzer UI reproduction — 2026-10-25

Completed step 1: ran CodexCloseMomentum through the visible NinjaTrader Strategy Analyzer Run command, then read Summary and Trades from its native WPF controls. This independently reproduced the preserved internal-engine result; no live orders were submitted.

## Configuration

- NQ DEC26, Last, Minute 1, instrument trading hours, Break at EOD enabled.
- Requested dates: 2026-09-28 through 2026-10-07.
- Anchor 0; FirstDate 20260929; LastDate 20261006.
- Standard fill resolution; slippage 2 ticks; commission disabled.
- Backtest account; quantity 1, long trades.

## Results

Native net profit **-$4,660**, gross profit $330, gross loss -$4,990, 6 trades, 1 winner, 5 losers; maximum drawdown $4,660. An external assumption of $5 per completed trade gives -$4,690, not a native commission calculation.

All six trades matched the preserved engine ledger on direction, quantity, entry/exit signal, entry/exit timestamps, entry/exit prices, and P&L. Timestamps below are Asia/Seoul; entry 04:31 and exit 05:01 on each listed date.

| Date | Entry | Exit | P&L |
|---|---:|---:|---:|
| 2026-09-30 | 30626.00 | 30614.75 | -225 |
| 2026-10-01 | 30833.75 | 30692.25 | -2830 |
| 2026-10-02 | 30804.75 | 30772.50 | -645 |
| 2026-10-03 | 31051.00 | 31067.50 | 330 |
| 2026-10-06 | 31354.75 | 31336.00 | -375 |
| 2026-10-07 | 31525.75 | 31480.00 | -915 |

One reporting difference remains: UI Bars is 31 while the internal ledger bars field is 30. Entry/exit timestamps agree (30-minute duration); do not treat the two bar-count fields as equivalent or claim every report field matches.

## Evidence and implementation

- `research/analyzer-ui-trades-2026-10-25.json`: preserved native UI observations.
- `research/analyzer-ui-comparison-2026-10-25.json`: six-trade comparison.
- `research/verify_analyzer_ui.py`: reproducible comparison against local `data/runner/close-momentum-batch2.json` (raw engine ledger is ignored runtime data).
- ResearchControl now reads SelectedText, updates TextBox bindings, invokes the real WPF Run command, and switches Summary/Trades. Analyzer actions are currently restricted to observed CodexCloseMomentum; this is a pilot, not universal Analyzer automation.
- Scratch compilation passed; installed compilation/reload succeeded with no errors and an existing CS8012 processor-architecture warning. The UI Run and both report views were exercised successfully.

An initial synthetic Click event did not execute the command. The corrected command invocation produced the report above. Assembly reload can invalidate the instrument object while retaining displayed text; reselect canonical NQ DEC26 and read back the instrument before any subsequent run.

The Analyzer was left on Summary. This validates execution reproducibility on this short historical sample, not profitability, recent-market suitability, out-of-sample performance, or Market Replay behavior. No Replay run was performed in this step.
