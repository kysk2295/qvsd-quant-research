# Dashboard metric display verification — 2026-10-27

The results page now opens on candidate/cost summaries instead of mixing preparation records with individual backtests. This is a display and saved-record integrity correction, not a new strategy evaluation or authorization to resume research.

## Findings

- Captured service state: 215 records, 161 current. 146 current records had numeric net profit, but only 14 had numeric top-level PF. The latest nine records were preparation/data work with empty performance metrics.
- Existing `params.assessment.extended_metrics_review.cases` contained 24 distinct summaries (12 candidates × two fees). The UI did not read these saved aggregate metrics.
- Aggregate scope is the listed run IDs and dates. OFI combines five runs; RSI includes a six-trade main run and a zero-trade extension. Aggregate PF must not be attached to every component.
- Some `status=rejected` executions had later sparse-sample research judgments. The old filter and judgment precedence concealed this distinction.

## Changes

- Separate candidate summaries, individual executions, and preparation/data records. Keep fee and observation dates visible; never sum different candidate/cost scopes.
- Deduplicate exact summary copies by report SHA, candidate, fee, run IDs and dates; quarantine conflicting copies of the same identity.
- Fill absent individual-run metrics only from a reconciled single-run summary. Preserve the original record and finite/null values.
- PF zero remains 0.00. No trades, no losing trades, and missing reports have different labels. No infinity or invented zero.
- Preserve both observed losses and sparse-sample limitations. Research filters use research judgments rather than historical execution labels.
- Detail views include daily results, cost sensitivity, concentration, and source provenance. Extra-cost arithmetic is explicitly separate from a new fill-path simulation; closed-trade drawdown is not a hard account-loss bound.

## Independent ledger checks

Existing historical fills, subtracting $10 roundtrip commission per contract; no additional native-slippage subtraction:

| Candidate | Observed period | Trades | Net | PF |
|---|---|---:|---:|---:|
| Bollinger | Oct 6–22 | 52 | $1,195 | 1.144324 |
| Stochastic | Oct 2–22 | 60 | −$585 | 0.941588 |
| OFI combined | Oct 2–22 | 60 | $165 | 1.015027 |
| RSI2 main | Main six trades, summary Oct 7–22 | 6 | $770 | 1.770000 |

The first three checks used saved ledgers on `origin/codex/windows-experiment-runner`. RSI used published `params.native_trade_ledger`: gross P&L [-240, 740, -240, -240, 1050, -240], one contract each. After $10 commission, total positive P&L is $1,770 and absolute negative P&L is $1,000. RSI $5 case independently reconciles to $800 and PF 1.816327. These are development observations, not independent OOS evidence.

## Verification and deployment

- 14 Node tests: pure result model and actual app script integration with independent synthetic fixtures.
- 7 Python server tests, including serving the result model before the application script and preserving authentication.
- Chrome local and production UI: 24 summaries, $10 filter yields 12; correct Bollinger/RSI figures, undefined CafeRetest15 PF, preparation split, and failure filter excludes deferred/invalid/unreviewed rows.
- Railway deployment `15317aa7-6e16-4b59-98e1-d15f95e655e3`: SUCCESS. Existing `/data` volume retained; no infrastructure or database mutation.
- Authenticated post-deploy state: all 215 complete run objects identical to the pre-deploy capture. Live JS/CSS hashes match local sources.
- No new backtests, future candidate P&L access, live orders, or automation restart.
- `graphify update .` could not run because its configured Python 3.12 interpreter is missing. Application tests and deployment succeeded independently.

Local audit captures are in `.omo/evidence/dashboard-metrics-20261027/`; authentication files remain Git-excluded and were not included in the deployment package.
