"""Conservative Last-mark equity bounds with uncertain fill timestamps.

No orders are resimulated. The ledger fixes entry/exit prices and final PnL.
Lower drawdown bounds use only certain holding ticks and closed-ledger anchors.
Upper bounds allow every Last price in the possible holding window, including
the price carried into it. This is a conservative envelope, not a feasible
worst-path optimization or an estimate of liquidation at bid/ask.
"""
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class FillWindow:
    entry_lo: int
    entry_hi: int
    exit_lo: int
    exit_hi: int
    entry_price: float
    exit_price: float
    side: int
    qty: int=1

def drawdown(values):
    values=np.asarray(values,dtype=float)
    return float(np.max(np.maximum.accumulate(values)-values)) if len(values) else 0.0

def audit_path(timestamps,prices,trades,fee,initial=150000.0,point_value=20.0):
    ts=np.asarray(timestamps,dtype=np.int64);px=np.asarray(prices,dtype=float)
    if len(ts)!=len(px) or not len(ts) or np.any(np.diff(ts)<0):raise ValueError('Ordered nonempty Last data required')
    if not np.all(np.isfinite(px)) or np.any(px<=0) or fee<0:raise ValueError('Invalid prices or fee')
    balance=initial;known=[initial];closed=[initial];all_lo=[np.array([initial])];all_hi=[np.array([initial])];times=[np.array([int(ts[0])],dtype=np.int64)];details=[];previous_exit=None
    for trade in trades:
        e0,e1,x0,x1=trade.entry_lo,trade.entry_hi,trade.exit_lo,trade.exit_hi
        if not e0<=e1<=x0<=x1:raise ValueError('Overlapping entry/exit uncertainty requires a different solver')
        if trade.side not in (-1,1) or trade.qty<=0:raise ValueError('Invalid direction/quantity')
        if previous_exit is not None and e0<=previous_exit:raise ValueError('Cross-trade time uncertainty overlaps')
        previous_exit=x1
        left=int(np.searchsorted(ts,e0,'left'));right=int(np.searchsorted(ts,x1,'right'))
        if left==0 or right>=len(ts):raise ValueError('Need Last context before entry and after exit')
        # A fill may occur between prints: include the Last price carried in.
        t=np.r_[np.int64(e0),ts[left:right]];p=np.r_[px[left-1],px[left:right]]
        opening=balance+(p-trade.entry_price)*trade.side*point_value*trade.qty-fee*trade.qty/2
        gross=(trade.exit_price-trade.entry_price)*trade.side*point_value*trade.qty
        after=balance+gross-fee*trade.qty
        lower=opening.copy();upper=opening.copy()
        # At equal timestamps event order is unobserved, even with fractions.
        before=t<=e1;after_possible=t>=x0
        lower[before]=np.minimum(lower[before],balance);upper[before]=np.maximum(upper[before],balance)
        lower[after_possible]=np.minimum(lower[after_possible],after);upper[after_possible]=np.maximum(upper[after_possible],after)
        certain=(t>e1)&(t<x0)
        sure=opening[certain]
        # Mandatory flat endpoints are exact under the fee convention.
        known.extend(sure.tolist());known.append(after);closed.append(after)
        all_lo.extend([lower,np.array([after])]);all_hi.extend([upper,np.array([after])]);times.extend([t,np.array([x1+1],dtype=np.int64)])
        details.append(dict(gross=gross,net=gross-fee*trade.qty,entry_window_ns=[int(e0),int(e1)],exit_window_ns=[int(x0),int(x1)],certain_holding_ticks=int(certain.sum()),possible_price_points=len(p),min_possible_equity=float(min(lower.min(),after,balance)),min_certain_equity=float(min([balance,after]+sure.tolist())),max_possible_equity=float(max(upper.max(),after,balance)),max_certain_equity=float(max([balance,after]+sure.tolist())),entry_fee=fee*trade.qty/2,exit_fee=fee*trade.qty/2))
        balance=after
    lo=np.concatenate(all_lo);hi=np.concatenate(all_hi);clock=np.concatenate(times);certain_values=np.array(known)
    dd_lo=drawdown(certain_values);dd_hi=float(np.max(np.maximum.accumulate(hi)-lo))
    closed_dd=drawdown(closed)
    if dd_lo+1e-7<closed_dd or dd_hi+1e-7<dd_lo:raise AssertionError('Invalid bounds')
    return dict(final_equity=balance,net=balance-initial,closed_trade_drawdown=closed_dd,holding_path_drawdown_lower=dd_lo,holding_path_drawdown_upper=dd_hi,min_equity_lower=float(lo.min()),min_equity_upper=float(certain_values.min()),max_equity_lower=float(certain_values.max()),max_equity_upper=float(hi.max()),worst_loss_from_start_lower=max(0,initial-float(certain_values.min())),worst_loss_from_start_upper=max(0,initial-float(lo.min())),trades=details,path=dict(timestamp_ns=clock,lower=lo,upper=hi,certain_values=certain_values))
