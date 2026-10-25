# Cost-path review and campaign freeze

## Findings from existing evidence

No native backtest or new strategy was run in this batch. Seven existing2/4-tick pairs were reconciled: Bollinger, MACD, and the five OFI windows. Every paired fill tuple was identical. Effective settings confirmed High/Tick1 and the requested slippage, with engine commission disabled. The installed bridge assigns the setting and verifies its readback.

[NinjaTrader's historical fill documentation](https://static.ninjatrader.com/support/helpGuides/nt8/understanding_historical_fill_.htm) bounds adverse slippage by the next fill bar's high/low and uses the secondary price series under High resolution. Single-tick Last bars have no intra-bar price range. The observations are consistent with this clipping; the engine's internal clipping branch was not instrumented. An additional native diagnostic would add little evidence now, so its budget is zero.

Keep three distinct cost channels:

1. Saved native Last-price fills: no incremental price change between these nominal settings.
2. Assumed $5/$10 round-trip fees: external arithmetic.
3. Additional2/4 adverse ticks **per fill**: arithmetic sensitivity on the saved ledger, not a changed execution path or an estimate of live cost.

Repricing fixed exits to historical bid/ask is not a complete alternative execution simulation. The previous October6 clock diagnostic does not restore fractional precision for all52 original Bollinger trades.

## Bollinger scope and risk

The tested policy takes the **first four eligible entries per day**, subject to flat-position, time, and risk filters. All13days reached the cap; the latest entry was11:16ET. OFI likewise reached four entries per day, with latest entry09:54ET. Results must not be generalized to unrestricted all-day indicator performance. The cap is unchanged.

| Assumed round-trip fee | Net | Additional4ticks/fill | Best day removed | Worst day |
|---|---:|---:|---:|---:|
| $5 | $1,455 | -$625 | $165 | -$990 |
| $10 | $1,195 | -$885 | -$75 | -$1,010 |

The -$900 rule checks realized PnL after an assumed $10 per completed trade before allowing another entry. It does not cap open losses, the final trade's loss, or account drawdown. Three dates lost more than$900. The$300 nominal pre-entry research assumption remains unchanged. Original per-trade MAE reaches12.5points, but it is not a continuous account-equity drawdown measurement. That path remains unverified for the original ledger.

## Campaign accounting

Linked194local telemetry identities and12archived dashboard seed identities, consistent with the supervisor's206dashboard rows. The ledger includes60queue records, including blocked/failed work, native attempts, cost and fill settings, source/data hashes, data repairs, manifest links, and recorded selection events. Native job IDs can repeat after assembly reload; joins use full-document identity or durable research IDs, never the short native ID alone. Input evidence snapshots were preserved before updating metadata.

These206records are **not206independent experiments**: archived/proxy records can share underlying observations, and cost variants do not add trades. Exact historical proposal times and unrecorded human ideas cannot be recovered. Existing historical decisions were not retroactively preregistered.

The earlier public-price study already exposed August14–October23. The entire interval is conservatively development data, including dates subsequently used for another strategy. The registry lists52observed session/context dates; no completed independent OOS dates exist. Switching strategies on those dates is part of model selection.

New candidate families, variants on observed dates, and extra native cost diagnostics now have zero active budget. The Python research bridge blocks new backtest submissions under this campaign control; read-only health/results remain available. Direct external tools must also honor the recorded budget. Four gate tests and18existing runner tests passed.

## Reserved future evaluation

One frozen Bollinger configuration is reserved for October26–November6:10weekday sessions. The decision time is **November7,2026,10:00KST**. Code, original manifest, rules, costs, risk, request, and decision criteria are hashed. The precise-clock strategy differs only in names and logging from the original trading logic; static parity passed.

This is a prospective historical-data validation plan, **not configured realtime paper execution**. No future data or returns exist yet. Reserved dates are not labeled completed OOS. The policy-blocked simulation-control route remains unavailable and is not retried.

- One reserved native attempt; zero currently released attempts; no uncertain-submission retry.
- One native fill setting, with fees and incremental friction assessed arithmetically, avoiding a known-uninformative duplicate.
- No candidate-PnL inspection before the fixed decision time. Quality-only audits may occur after sessions close.
- Require all10sessions, timezone/DST-aware390-minute coverage, source and signal parity, full-precision clocks, and raw-Last marked-equity reconstruction. Missing dates are not replaced or skipped.
- Further consideration requires positive high-fee plus additional4-tick sensitivity and positive high-fee best-day-removed net. Passing yields at most eligibility for longer preregistered validation, never live approval or statistical proof from10days.
- Any rule/cost/risk/selection change or outcome peek invalidates the reservation for the unchanged-plan claim. No automatic window extension or candidate replacement.
- Existing-entitlement downloads only, at most one submission/date and three/date chunk; no purchase, recurring job, or live order.

Current preflight confirms unchanged hashes and no observed-date overlap; all10prepared future dates are missing, and the decision time has not arrived. A counted execution packet must be prepared after those conditions are met. Paper execution and account-level risk validation remain separate unresolved requirements.

Artifacts: `campaign-trial-registry.json`, `campaign-evidence-snapshot-index.json`, `campaign-search-control.json`, `bollinger-cost-path-review.json`, `bollinger-prospective-plan.json`, `bollinger-prospective-preflight.json`, and `campaign-review-summary.json` under `research/`. Cost metadata ACKs:14; future-plan metadata ACKs:2. Original metrics and assessments remain preserved.
