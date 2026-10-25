# Historical execution clock, costs and recovered acquisition

The installed bridge's Backtest snapshot passes `Trade.Entry.Time` and `Trade.Exit.Time` through `Tm`, which formats `yyyy-MM-ddTHH:mm:ss`. This discards fractional seconds. Completed strategy references are cleared during teardown; the missing fractions cannot be recovered from previously saved JSON.

A separately preregistered diagnostic reproduced only the earliest Bollinger date, Oct6, with unchanged trading logic and additional prints of raw callback/Execution/Trade timestamps and .NET ticks. It used one native run and is **not a new performance observation**. Four trades exactly matched the original ledger. All8 simulated executions had fractional seconds; callback and Trade times matched. Every execution timestamp and price also matched an original Last event in the recorded L1 file. All4entries used the first Last tick at or after the signal, at offsets60/28/4/4ms.

This distinguishes output truncation from an always-whole-second engine clock for this HighTick1 case. It does not establish live execution, real routing latency, order queue behavior, or the precision of other fill modes. Adding decimal formatting alone would not have established these results. The historical primary-bar clock remains minute-based while the simulated execution clock follows the finer fill series.

Strictly preceding bid/ask observations, ages, sizes and same-timestamp quote-event counts are preserved in `research/execution-clock-audit.json`. No shared ordering between a simulated execution and recorded quotes at the identical timestamp is proved. Touch-price substitution at fixed original exit times is only diagnostic: different entries would move stops and could change subsequent exits. No revised strategy profitability is claimed from that substitution.

## Cost break-even

Both strategies have52unique observed trades. Cost variants do not double this sample; the diagnostic adds zero. For one NQ contract, two fills pertrade and$5/tick, the following is the **additional total adverse cost perfill beyond native fills** that consumes all net profit:

| Candidate | After$5roundtrip fee | After$10roundtrip fee |
|---|---:|---:|
| OFI,13observed sessions |2.510ticks|2.010ticks|
| Bollinger return,13observed sessions |2.798ticks|2.298ticks|

Native requested2/4tick slippage previously produced identical actual fill tuples. Its nominal net difference was fees only. Arithmetic extra ticks are separate scenarios. If prices are replaced by bid/ask touch prices, do not subtract that same full spread again. Neither strategy has established an executable net edge. RSI, OFI and Bollinger remain deferred.

## Historical Data recovery

The UI problem was multiple windows with the same Historical Data title, not a policy refusal. Source inspection showed the existing supported `title|hwnd` selector. A previously observed window handle was selected; its observed instrument/date/download controls were used, without creating another window or changing safeguards. One download submission requested Oct5. The download completed and produced a124,638,732byte NRD file. Only that new file was decoded locally; no retry of the known corrupt Oct23file occurred.

The new Oct5 file contains9,126,553L1 rows. Decoder/header integrity checks passed,390regular-session minutes contain quotes,367minutes pass the unchanged OFI quality gate, and settled crossed groups were zero. This is newly acquired **historical extension data**, not prospective validation. Original NRD and parquet hashes are preserved. No native strategy outcome for Oct5 was computed in this batch.

Next: independently verify/import Oct5 Last data for native fill coverage, freeze the separate OFI feature CSV and strategy hash, then preregister at most2cost-condition historical tests under the unchanged rule. No previously evaluated OFI date needs repeating. Raw simulated timestamps should be retained in new diagnostic-aware records, while older records stay immutable.

One diagnostic result ACK and9review metadata ACKs were confirmed, including new acquisition evidence. No order/account endpoint query, Playback activation, live trade, purchase or recurring task was used. The finite worker ended idle.
