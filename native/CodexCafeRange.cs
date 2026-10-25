using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Strategies
{
    // Research interpretation of repository backtest.py; native fills are authoritative.
    public class CodexCafeRange : Strategy
    {
        [NinjaScriptProperty, Range(1,3)] public int Variant {get;set;}
        [NinjaScriptProperty, Range(15,30)] public int RangeMinutes {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private TimeZoneInfo eastern;
        private DateTime day=DateTime.MinValue, previous=DateTime.MinValue;
        private readonly Queue<double> tr=new Queue<double>();
        private readonly List<double> vwaps=new List<double>();
        private double prevClose,hi,lo,pv,vol,dayStartProfit;
        private bool initialized,gap,pending,reported;
        private int count,entries,armed,armedBar;
        protected override void OnStateChange()
        {
            if(State==State.SetDefaults)
            {
                Name="CodexCafeRange"; Variant=1; RangeMinutes=15;
                FirstDate=20260929; LastDate=20261006;
                Calculate=Calculate.OnBarClose; BarsRequiredToTrade=14;
                EntriesPerDirection=1; IsExitOnSessionCloseStrategy=true;
                IsInstantiatedOnEachOptimizationIteration=true;
            }
            else if(State==State.DataLoaded)
            {
                eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute || BarsPeriod.Value!=5)
                    throw new InvalidOperationException("Requires five-minute bars");
            }
        }
        protected override void OnBarUpdate()
        {
            if(State!=State.Historical || Account==null || Account.Name!=Account.BackTestAccountName) return;
            if(Instrument.MasterInstrument.Name!="NQ") throw new InvalidOperationException("NQ only");
            double c=Close[0],h=High[0],l=Low[0];
            tr.Enqueue(initialized ? Math.Max(h-l,Math.Max(Math.Abs(h-prevClose),Math.Abs(l-prevClose))) : h-l);
            if(tr.Count>14) tr.Dequeue(); prevClose=c; initialized=true;
            DateTime end=TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(Time[0],DateTimeKind.Unspecified),Core.Globals.GeneralOptions.TimeZoneInfo,eastern);
            DateTime start=end.AddMinutes(-5);
            if(start.Date!=day)
            {
                day=start.Date; count=entries=armed=0; hi=double.MinValue;lo=double.MaxValue;
                pv=vol=0;gap=pending=reported=false;previous=DateTime.MinValue;vwaps.Clear();
                dayStartProfit=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
            }
            int date=day.Year*10000+day.Month*100+day.Day;
            if(date<FirstDate || date>LastDate) return;
            int m=start.Hour*60+start.Minute;
            if(m<570 || m>=960) return;
            if((count==0 && m!=570) || (previous!=DateTime.MinValue && start!=previous.AddMinutes(5))) gap=true;
            previous=start; count++;
            pv+=(h+l+c)/3*Volume[0];vol+=Volume[0];double vwap=vol>0 ? pv/vol:c; vwaps.Add(vwap);
            int n=(Variant==3 ? 60:RangeMinutes)/5;
            if(count<=n){hi=Math.Max(hi,h);lo=Math.Min(lo,l);return;}
            // Submit at 15:55. Historical execution occurs on the next bar; NT stamps its end.
            if(end.TimeOfDay>=new TimeSpan(15,55,0))
            {
                if(Position.MarketPosition==MarketPosition.Long) ExitLong("TimeExit","L");
                if(Position.MarketPosition==MarketPosition.Short) ExitShort("TimeExit","S");
                if(!reported){Print("AUDIT "+date+" bars="+count+" gap="+gap+" entries="+entries);reported=true;}
                return;
            }
            if(gap || pending || Position.MarketPosition!=MarketPosition.Flat || tr.Count<14 || m>=895 || entries>=4) return;
            if(SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit-dayStartProfit<=-900) return;
            double atr=tr.Average(), buffer=Math.Max(TickSize,.05*atr),mid=(hi+lo)/2,stop=0,target=0;
            bool lf=c>vwap && vwaps.Count>=4 && vwap>vwaps[vwaps.Count-4];
            bool sf=c<vwap && vwaps.Count>=4 && vwap<vwaps[vwaps.Count-4];
            int side=0;
            if(Variant==1)
            {
                if(Close[1]<=hi && c>hi+buffer && lf){side=1;stop=c-Math.Max(1.5*atr,.25*(hi-lo));}
                if(Close[1]>=lo && c<lo-buffer && sf){side=-1;stop=c+Math.Max(1.5*atr,.25*(hi-lo));}
            }
            else if(Variant==2)
            {
                if(armed!=0 && CurrentBar-armedBar>6) armed=0;
                if(armed!=0 && CurrentBar>armedBar)
                {
                    if(armed==1 && l<=hi+buffer && c>hi+buffer && lf){side=1;stop=Math.Min(l,hi)-buffer;armed=0;}
                    else if(armed==-1 && h>=lo-buffer && c<lo-buffer && sf){side=-1;stop=Math.Max(h,lo)+buffer;armed=0;}
                    else if((armed==1 && c<mid)||(armed==-1 && c>mid)) armed=0;
                }
                if(armed==0 && side==0)
                {
                    if(Close[1]<=hi && c>hi+buffer && lf){armed=1;armedBar=CurrentBar;}
                    else if(Close[1]>=lo && c<lo-buffer && sf){armed=-1;armedBar=CurrentBar;}
                }
            }
            else
            {
                if(h>hi+buffer && c>mid && c<hi){side=-1;stop=h+buffer;target=mid;}
                else if(l<lo-buffer && c>lo && c<mid){side=1;stop=l-buffer;target=mid;}
            }
            if(side==0) return;
            stop=(side==1 ? Math.Floor(stop/TickSize):Math.Ceiling(stop/TickSize))*TickSize;
            double distance=side*(c-stop);
            // Conservative pre-submission estimate, fixed across cost cases; gaps can exceed budget.
            double risk=(distance+2.0)*20+10;
            if(distance<2*TickSize || risk>300){Print("SIZE_REJECT "+date+" risk="+risk);return;}
            if(Variant!=3) target=c+side*2*distance;
            target=Instrument.MasterInstrument.RoundToTickSize(target);
            if(side*(target-c)<distance) return;
            string signal=side==1 ? "L":"S";
            SetStopLoss(signal,CalculationMode.Price,stop,false);
            SetProfitTarget(signal,CalculationMode.Price,target);
            pending=true;entries++;
            if(side==1) EnterLong(1,signal);else EnterShort(1,signal);
        }
        protected override void OnOrderUpdate(Order order,double limitPrice,double stopPrice,int quantity,int filled,double averageFillPrice,OrderState orderState,DateTime time,ErrorCode error,string comment)
        {
            if((order.Name=="L"||order.Name=="S") && (orderState==OrderState.Filled||orderState==OrderState.Cancelled||orderState==OrderState.Rejected)) pending=false;
            if(error!=ErrorCode.NoError) Print("ORDER_ERROR "+error+" "+comment);
        }
    }
}
