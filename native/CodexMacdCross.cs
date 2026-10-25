using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Strategies
{
    // BEGIN PURE MACD MATH
    public static class CodexMacdMath
    {
        public static double[] Step(double close,double fast,double slow,double signal,bool first)
        {
            if(first)return new double[]{close,close,0,0};
            fast+=(close-fast)*2.0/13;slow+=(close-slow)*2.0/27;
            double line=fast-slow;signal+=(line-signal)*2.0/10;
            return new double[]{fast,slow,signal,line-signal};
        }
        public static int Cross(double previous,double current)
        {return previous<=0 && current>0?1:previous>=0 && current<0?-1:0;}
    }
    // END PURE MACD MATH

    public class CodexMacdCross : Strategy
    {
        [NinjaScriptProperty,Range(26,26)] public int SlowLength {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private double fast,slow,signalEma,hist;
        private readonly Dictionary<string,int> counts=new Dictionary<string,int>();
        private TimeZoneInfo eastern;
        private DateTime day=DateTime.MinValue,previous=DateTime.MinValue;
        private bool gap,pending,reported;
        private int count,entries,entryBar=-1,startTrades;
        private double startProfit;
        private void Note(string reason){if(!counts.ContainsKey(reason))counts[reason]=0;counts[reason]++;}
        protected override void OnStateChange()
        {
            if(State==State.SetDefaults)
            {
                Name="CodexMacdCross";SlowLength=26;FirstDate=20261007;LastDate=20261022;
                Calculate=Calculate.OnBarClose;BarsRequiredToTrade=1;EntriesPerDirection=1;
                IsExitOnSessionCloseStrategy=true;IsInstantiatedOnEachOptimizationIteration=true;
            }
            else if(State==State.DataLoaded)
            {
                if(Account==null || Account.Name!=Account.BackTestAccountName)throw new InvalidOperationException("Backtest account only");
                if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute || BarsPeriod.Value!=1)throw new InvalidOperationException("One-minute bars required");
                eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");

            }
        }
        protected override void OnBarUpdate()
        {
            if(State!=State.Historical || Account==null || Account.Name!=Account.BackTestAccountName)return;
            if(Instrument.MasterInstrument.Name!="NQ")throw new InvalidOperationException("NQ only");
            DateTime raw=DateTime.SpecifyKind(Time[0],DateTimeKind.Unspecified);
            DateTime utc=TimeZoneInfo.ConvertTimeToUtc(raw,Core.Globals.GeneralOptions.TimeZoneInfo);
            DateTime end=TimeZoneInfo.ConvertTimeFromUtc(utc,eastern),start=end.AddMinutes(-1);
            if(day!=start.Date)
            {day=start.Date;previous=DateTime.MinValue;count=entries=0;gap=pending=reported=false;counts.Clear();fast=slow=signalEma=hist=0;startProfit=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;startTrades=SystemPerformance.AllTrades.Count;}
            int date=day.Year*10000+day.Month*100+day.Day,m=end.Hour*60+end.Minute;
            if(date<FirstDate || date>LastDate || start.TimeOfDay<new TimeSpan(9,30,0)||start.TimeOfDay>=new TimeSpan(16,0,0))return;
            if((count==0 && start.TimeOfDay!=new TimeSpan(9,30,0))||(previous!=DateTime.MinValue && start!=previous.AddMinutes(1)))gap=true;
            previous=start;count++;
            double previousHist=hist;double[] values=CodexMacdMath.Step(Close[0],fast,slow,signalEma,count==1);
            fast=values[0];slow=values[1];signalEma=values[2];hist=values[3];int direction=count>1?CodexMacdMath.Cross(previousHist,hist):0;
            Print(string.Format(CultureInfo.InvariantCulture,"MACD {0:yyyy-MM-ddTHH:mm:ss} close={1:R} fast={2:R} slow={3:R} signal={4:R} hist={5:R} side={6}",end,Close[0],fast,slow,signalEma,hist,direction));
            bool timed=(entryBar>=0 && CurrentBar-entryBar>=10)||m>=955;
            if(Position.MarketPosition==MarketPosition.Long && (timed || hist<0)){ExitLong("TimeExit","L");Note("exit_submitted");}
            if(Position.MarketPosition==MarketPosition.Short && (timed || hist>0)){ExitShort("TimeExit","S");Note("exit_submitted");}
            if(m>=960 && !reported)
            {
                foreach(Trade t in SystemPerformance.AllTrades)Print("CLOCK_TRADE|"+t.Entry.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+t.Entry.Time.Ticks+"|"+t.Exit.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+t.Exit.Time.Ticks);
Print("AUDIT "+date+" bars="+count+" gap="+gap+" entries="+entries);Print("COUNTS "+date+" "+string.Join(" ",counts.OrderBy(x=>x.Key).Select(x=>x.Key+"="+x.Value)));reported=true;}
            if(gap){Note("session_gap");return;}
            if(m<650 || m>925){Note("entry_time_filter");return;}
            if(pending || Position.MarketPosition!=MarketPosition.Flat){Note("position_or_pending");return;}
            if(entries>=4){Note("entry_limit");return;}
            double realized=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit-startProfit-10*(SystemPerformance.AllTrades.Count-startTrades);
            if(realized<=-900){Note("daily_loss_limit");return;}
            if(count<80){Note("warmup");return;}
            int side=direction;if(side==0){Note("no_crossing");return;}
            string signal=side==1?"L":"S";
            Print(string.Format(CultureInfo.InvariantCulture,"SIGNAL {0:yyyy-MM-ddTHH:mm:ss} side={1} close={2:R} fast={3:R} slow={4:R} hist={5:R}",end,signal,Close[0],fast,slow,hist));
            Print("CLOCK_SUBMIT|"+Time[0].ToString("o",CultureInfo.InvariantCulture)+"|"+Time[0].Ticks+"|"+signal+"|"+Close[0].ToString("R",CultureInfo.InvariantCulture));
            SetStopLoss(signal,CalculationMode.Ticks,48,false);pending=true;entries++;Note("entry_submitted");
            if(side==1)EnterLong(1,signal);else EnterShort(1,signal);
        }
        protected override void OnOrderUpdate(Order order,double limitPrice,double stopPrice,int quantity,int filled,double averageFillPrice,OrderState orderState,DateTime time,ErrorCode error,string comment)
        {
            if((order.Name=="L"||order.Name=="S")&&(orderState==OrderState.Filled||orderState==OrderState.Cancelled||orderState==OrderState.Rejected))pending=false;
            if(error!=ErrorCode.NoError)Print("ORDER_ERROR "+error+" "+comment);
        }
        protected override void OnExecutionUpdate(Execution execution,string executionId,double price,int quantity,MarketPosition marketPosition,string orderId,DateTime time)
        {
            Print("CLOCK_EXEC|"+execution.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+execution.Time.Ticks+"|"+time.ToString("o",CultureInfo.InvariantCulture)+"|"+time.Ticks+"|"+Time[0].ToString("o",CultureInfo.InvariantCulture)+"|"+execution.Order.Name+"|"+price.ToString("R",CultureInfo.InvariantCulture)+"|"+quantity+"|"+State);
            if(execution.Order!=null && (execution.Order.Name=="L"||execution.Order.Name=="S") && marketPosition!=MarketPosition.Flat)entryBar=CurrentBar;}
    }
}
