"""Compare preserved WPF observations with the existing engine ledger."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
ui = json.loads((root / 'research/analyzer-ui-trades-2026-10-25.json').read_text(encoding='utf-8'))
controls = {c['id']: c for c in ui['controls']}
engine = json.loads((root / 'data/runner/close-momentum-batch2.json').read_text(encoding='utf-8'))[0]
rows = []
for i, expected in enumerate(engine['trades']):
    base = 189 + 23 * i
    val = lambda offset: controls[base + offset]['fields']['Value']
    pnl_text = controls[364 + 21 * i]['fields']['Text']
    actual = dict(side=val(4), qty=int(val(5)), entryPrice=float(val(6)),
                  exitPrice=float(val(7)), entryTime=val(8)[:19], exitTime=val(9)[:19],
                  entryName=val(10), exitName=val(11),
                  pnl=float(pnl_text.replace('$', '').replace(',', '')))
    differences = {k: {'ui': v, 'engine': expected[k]} for k, v in actual.items() if v != expected[k]}
    rows.append({'trade': i + 1, **actual, 'differences': differences,
                 'uiBars': int(val(22)), 'engineBars': expected['bars']})
result = {'strategy': engine['strategy'], 'matchedTrades': sum(not r['differences'] for r in rows),
          'uiNetProfit': sum(r['pnl'] for r in rows), 'engineNetProfit': engine['summary']['netProfit'],
          'barsCaveat': 'UI displays 31 bars; engine ledger reports 30. Duration fields are not equivalent.',
          'rows': rows}
(root / 'research/analyzer-ui-comparison-2026-10-25.json').write_text(json.dumps(result, indent=2) + '\n')
assert len(rows) == 6 and result['matchedTrades'] == 6
assert result['uiNetProfit'] == result['engineNetProfit'] == -4660
print(json.dumps({k:v for k,v in result.items() if k != 'rows'}, indent=2))
