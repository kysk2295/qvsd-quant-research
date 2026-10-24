import unittest, copy
from backtest import exit_fill,load,run,SPECS
class ExecutionTests(unittest.TestCase):
 def test_long_ambiguous_bar_stop_first(self):
  self.assertEqual(exit_fill(dict(o=100,h=112,l=90),1,95,110,.5),(94.5,'stop'))
 def test_short_ambiguous_bar_stop_first(self):
  self.assertEqual(exit_fill(dict(o=100,h=112,l=90),-1,105,90,.5),(105.5,'stop'))
 def test_long_gap_stop(self):
  self.assertEqual(exit_fill(dict(o=90,h=112,l=89),1,95,110,.5),(89.5,'gap_stop'))
 def test_short_gap_stop(self):
  self.assertEqual(exit_fill(dict(o=112,h=113,l=90),-1,105,90,.5),(112.5,'gap_stop'))
 def test_target_gap_no_price_improvement(self):
  self.assertEqual(exit_fill(dict(o=112,h=113,l=100),1,95,110,.5),(110,'target'))
 def test_no_fill(self):
  self.assertIsNone(exit_fill(dict(o=100,h=104,l=96),1,95,110,.5))
 def test_ledger_and_risk(self):
  for sym in SPECS:
   ss,_=load(sym)
   for mode in ['breakout','retest','failed_ib']:
    ts,ds,_=run(ss,sym,mode)
    self.assertAlmostEqual(sum(t['pnl'] for t in ts),sum(d['pnl'] for d in ds))
    self.assertTrue(all(d['entries']<=4 for d in ds))
    for t in ts:
     self.assertTrue(1<=t['qty']<=10)
     self.assertGreaterEqual(t['start_i'],13 if mode=='failed_ib' else 4)
     risk=(abs(t['entry']-t['stop'])*SPECS[sym]['point']+2*SPECS[sym]['tick']*SPECS[sym]['point']+2.5)*t['qty']
     self.assertLessEqual(risk,300.00001)
 def test_future_prices_do_not_change_earlier_closed_trades(self):
  ss,_=load('NQ');day=list(ss)[10];original={day:ss[day]};changed=copy.deepcopy(original)
  for b in changed[day]:
   if b['minute']>=840:
    for k in ['o','h','l','c']:b[k]+=500
  for mode in ['breakout','retest','failed_ib']:
   a,_,_=run(original,'NQ',mode);b,_,_=run(changed,'NQ',mode)
   before=lambda rows:[t for t in rows if int(t['exit_time'][11:13])<14]
   self.assertEqual(before(a),before(b))
if __name__=='__main__':unittest.main()
