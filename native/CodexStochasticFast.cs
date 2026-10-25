using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Strategies
{
    // BEGIN PURE STOCH MATH
    public static class CodexStochMath
    {
        public static double Raw(double close,double high,double low)
        {return high>low?100*(close-low)/(high-low):double.NaN;}
        public static int Cross(double pk,double pd,double k,double d)
        {return pk<=pd&&k>d&&k<20?1:pk>=pd&&k<d&&k>80?-1:0;}
    }
    // END PURE STOCH MATH
    public class CodexStochasticFast : Strategy
    {
        [NinjaScriptProperty,Range(14,14)] public int KLength {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private readonly Queue<double> highs=new Queue<double>(),lows=new Queue<double>(),ks=new Queue<double>();
        private readonly Dictionary<string,int> counts=new Dictionary<string,int>();
        private TimeZoneInfo eastern;
        private DateTime day=DateTime.MinValue,previous=DateTime.MinValue;
        private bool gap,pending,reported;
        private int count,entries,entryBar=-1,startTrades;
        private double k=double.NaN,d=double.NaN,startProfit;
        private void Note(string reason){if(!counts.ContainsKey(reason))counts[reason]=0;counts[reason]++;}
        protected override void OnStateChange()
        {
            if(State==State.SetDefaults){Name="CodexStochasticFast";KLength=14;FirstDate=20261002;LastDate=20261022;Calculate=Calculate.OnBarClose;BarsRequiredToTrade=1;EntriesPerDirection=1;IsExitOnSessionCloseStrategy=true;IsInstantiatedOnEachOptimizationIteration=true;}
            else if(State==State.DataLoaded){if(Account==null||Account.Name!=Account.BackTestAccountName)throw new InvalidOperationException("Backtest only");if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute||BarsPeriod.Value!=1)throw new InvalidOperationException("Minute1 required");eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");}
        }
        protected override void OnBarUpdate()
        {
            if(State!=State.Historical||Account==null||Account.Name!=Account.BackTestAccountName)return;
            if(Instrument.MasterInstrument.Name!="NQ")throw new InvalidOperationException("NQ only");
            DateTime end=TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(Time[0],DateTimeKind.Unspecified),Core.Globals.GeneralOptions.TimeZoneInfo,eastern),start=end.AddMinutes(-1);
            int date=start.Year*10000+start.Month*100+start.Day,m=end.Hour*60+end.Minute;
            if(date<FirstDate||date>LastDate||start.TimeOfDay<new TimeSpan(9,30,0)||start.TimeOfDay>=new TimeSpan(16,0,0))return;
            if(day!=start.Date){day=start.Date;previous=DateTime.MinValue;count=entries=0;entryBar=-1;gap=pending=reported=false;counts.Clear();highs.Clear();lows.Clear();ks.Clear();k=d=double.NaN;startProfit=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;startTrades=SystemPerformance.AllTrades.Count;}
            if((count==0&&start.TimeOfDay!=new TimeSpan(9,30,0))||(previous!=DateTime.MinValue&&start!=previous.AddMinutes(1)))gap=true;
            previous=start;count++;
            double pk=k,pd=d;highs.Enqueue(High[0]);lows.Enqueue(Low[0]);if(highs.Count>14){highs.Dequeue();lows.Dequeue();}
            k=highs.Count==14?CodexStochMath.Raw(Close[0],highs.Max(),lows.Min()):double.NaN;
            if(double.IsNaN(k))ks.Clear();else{ks.Enqueue(k);if(ks.Count>3)ks.Dequeue();}
            d=ks.Count==3?ks.Average():double.NaN;
            int side=CodexStochMath.Cross(pk,pd,k,d);
            Print(string.Format(CultureInfo.InvariantCulture,"STOCH {0:yyyy-MM-ddTHH:mm:ss} high={1:R} low={2:R} close={3:R} k={4:R} d={5:R} side={6}",end,High[0],Low[0],Close[0],k,d,side));
            bool timed=(entryBar>=0&&CurrentBar-entryBar>=20)||m>=955;
            if(timed&&Position.MarketPosition==MarketPosition.Long){ExitLong("TimeExit","L");Note("exit_submitted");}
            if(timed&&Position.MarketPosition==MarketPosition.Short){ExitShort("TimeExit","S");Note("exit_submitted");}
            if(m==960&&!reported){foreach(Trade t in SystemPerformance.AllTrades)Print("CLOCK_TRADE|"+t.Entry.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+t.Entry.Time.Ticks+"|"+t.Exit.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+t.Exit.Time.Ticks);Print("AUDIT "+date+" bars="+count+" gap="+gap+" entries="+entries);Print("COUNTS "+date+" "+string.Join(" ",counts.OrderBy(x=>x.Key).Select(x=>x.Key+"="+x.Value)));reported=true;}
            if(gap){Note("session_gap");return;}
            if(m<590||m>925){Note("entry_time_filter");return;}
            if(pending||Position.MarketPosition!=MarketPosition.Flat){Note("position_or_pending");return;}
            if(entries>=4){Note("entry_limit");return;}
            double realized=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit-startProfit-10*(SystemPerformance.AllTrades.Count-startTrades);
            if(realized<=-900){Note("daily_loss_limit");return;}
            if(double.IsNaN(d)||double.IsNaN(pd)){Note("warmup_or_zero_width");return;}
            if(side==0){Note("no_extreme_cross");return;}
            string signal=side==1?"L":"S";
            Print(string.Format(CultureInfo.InvariantCulture,"SIGNAL {0:yyyy-MM-ddTHH:mm:ss} side={1} close={2:R} k={3:R} d={4:R}",end,signal,Close[0],k,d));
            SetStopLoss(signal,CalculationMode.Ticks,48,false);SetProfitTarget(signal,CalculationMode.Ticks,96);pending=true;entries++;Note("entry_submitted");
            if(side==1)EnterLong(1,signal);else EnterShort(1,signal);
        }
        protected override void OnOrderUpdate(Order order,double limitPrice,double stopPrice,int quantity,int filled,double averageFillPrice,OrderState orderState,DateTime time,ErrorCode error,string comment)
        {if((order.Name=="L"||order.Name=="S")&&(orderState==OrderState.Filled||orderState==OrderState.Cancelled||orderState==OrderState.Rejected))pending=false;if(error!=ErrorCode.NoError)Print("ORDER_ERROR "+error+" "+comment);}
        protected override void OnExecutionUpdate(Execution execution,string executionId,double price,int quantity,MarketPosition marketPosition,string orderId,DateTime time)
        {Print("CLOCK_EXEC|"+execution.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+execution.Time.Ticks+"|"+time.ToString("o",CultureInfo.InvariantCulture)+"|"+time.Ticks+"|"+Time[0].ToString("o",CultureInfo.InvariantCulture)+"|"+execution.Order.Name+"|"+price.ToString("R",CultureInfo.InvariantCulture)+"|"+quantity+"|"+State);if((execution.Order.Name=="L"||execution.Order.Name=="S")&&marketPosition!=MarketPosition.Flat)entryBar=CurrentBar;}
    }
}
