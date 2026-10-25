# NQ Replay acquisition — 2026-10-25

Used NinjaTrader Historical Data > Get Market Replay data after disconnecting Playback. Native WPF control targeting was repaired to accept an explicit observed window handle; ambiguous duplicate windows no longer prevent selecting the intended window. Windows screen capture failed, so the native research control interface performed the UI actions.

## Download evidence

| Replay date | Bytes | Validation |
|---|---:|---|
| 2026-10-20 | 241,929,637 | Download complete; header declares L1/L2; decoding pending |
| 2026-10-21 | 223,213,591 | Decoded L1 15,826,128 rows and L2 31,408,386 rows; header consistency checks passed |
| 2026-10-23 | 70,842,732 | Decoder/header volume and price mismatch; excluded from research; root cause unresolved; header has no L2 |

21 October timestamps span 2026-10-21 04:00:00.024 UTC through 2026-10-22 03:59:59.996 UTC. Both streams have zero backward timestamps and zero negative volumes. This does not establish absence of all feed gaps or valid reconstructed depth. The date is the Replay file date, not an asserted exchange session boundary. Raw download hashes and row audit remain in ignored data/runner/replay-*-audit.json; licensed raw data is not committed.

## Other diagnostic findings

The explicit-bars native pilot still loaded September 30 through October 2 for a September 28–29 request. It remains rejected. Time-zone reporting and warmup/trade separation were improved, but the historical loading issue is not declared fixed. Out-of-window trades are now counted even when bar coverage is invalid.

Opening-range breakout zero-trade results were sizing rejections, not absence of signals. Earlier period: 91 attempts for OR15 and 85 for OR30, all sizing-rejected. Recent period: 34 attempts for OR15 and 26 for OR30, all sizing-rejected. Recent minimum one-contract risk was $680 under base costs and $705 under stress costs, exceeding the configured $300 risk budget. No parameters were optimized to force trades.

Validation: runner 18 tests and research 9 tests passed (research tests must run with unittest discovery from research because of their local import). No live orders, no profitable strategy adoption, no independent out-of-sample or forward-test claim.

Next research gate: decode October 20, investigate October 23 with an independent/native decoder, reconstruct and validate L2 state before testing order-flow hypotheses. Newly acquired data must not silently enter previously fingerprinted experiments.
