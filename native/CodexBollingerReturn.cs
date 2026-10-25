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
    // BEGIN PURE BAND MATH
    public static class CodexBandMath
    {
        public static double[] Bands(double[] values)
        {
            if(values.Length!=20)throw new InvalidOperationException("20closes required");
            double mean=values.Average(),sum=0;
            foreach(double v in values)sum+=(v-mean)*(v-mean);
            double dev=2*Math.Sqrt(sum/20.0);return new double[]{mean,mean-dev,mean+dev};
        }
        public static int Signal(double prev,double pl,double pu,double close,double lower,double upper)
        {return prev<=pl && close>lower?1:prev>=pu && close<upper?-1:0;}
    }
    // END PURE BAND MATH

    public class CodexBollingerReturn : Strategy
    {
        [NinjaScriptProperty,Range(20,20)] public int BandLength {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private readonly Queue<double> closes=new Queue<double>();
        private double prevClose,prevLower,prevUpper;
        private bool havePrevious;
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
                Name="CodexBollingerReturn";BandLength=20;FirstDate=20261007;LastDate=20261022;
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
            {day=start.Date;previous=DateTime.MinValue;count=entries=0;gap=pending=reported=false;counts.Clear();closes.Clear();havePrevious=false;startProfit=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;startTrades=SystemPerformance.AllTrades.Count;}
            int date=day.Year*10000+day.Month*100+day.Day,m=end.Hour*60+end.Minute;
            if(date<FirstDate || date>LastDate || start.TimeOfDay<new TimeSpan(9,30,0)||start.TimeOfDay>=new TimeSpan(16,0,0))return;
            if((count==0 && start.TimeOfDay!=new TimeSpan(9,30,0))||(previous!=DateTime.MinValue && start!=previous.AddMinutes(1)))gap=true;
            previous=start;count++;
            closes.Enqueue(Close[0]);if(closes.Count>20)closes.Dequeue();
            double[] bands=closes.Count==20?CodexBandMath.Bands(closes.ToArray()):null;
            int direction=bands!=null && havePrevious?CodexBandMath.Signal(prevClose,prevLower,prevUpper,Close[0],bands[1],bands[2]):0;
            Print(string.Format(CultureInfo.InvariantCulture,"BAR {0:yyyy-MM-ddTHH:mm:ss} close={1:R} mean={2:R} lower={3:R} upper={4:R} side={5}",end,Close[0],bands==null?0:bands[0],bands==null?0:bands[1],bands==null?0:bands[2],direction));
            if(bands!=null){prevClose=Close[0];prevLower=bands[1];prevUpper=bands[2];havePrevious=true;}
            bool timed=(entryBar>=0 && CurrentBar-entryBar>=10)||m>=955;
            if(Position.MarketPosition==MarketPosition.Long && (timed || (bands!=null && Close[0]>=bands[0]))){ExitLong("TimeExit","L");Note("exit_submitted");}
            if(Position.MarketPosition==MarketPosition.Short && (timed || (bands!=null && Close[0]<=bands[0]))){ExitShort("TimeExit","S");Note("exit_submitted");}
            if(m>=960 && !reported)
            {Print("AUDIT "+date+" bars="+count+" gap="+gap+" entries="+entries);Print("COUNTS "+date+" "+string.Join(" ",counts.OrderBy(x=>x.Key).Select(x=>x.Key+"="+x.Value)));reported=true;}
            if(gap){Note("session_gap");return;}
            if(m<591 || m>925){Note("entry_time_filter");return;}
            if(pending || Position.MarketPosition!=MarketPosition.Flat){Note("position_or_pending");return;}
            if(entries>=4){Note("entry_limit");return;}
            double realized=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit-startProfit-10*(SystemPerformance.AllTrades.Count-startTrades);
            if(realized<=-900){Note("daily_loss_limit");return;}
            if(bands==null || count<21){Note("warmup");return;}
            int side=direction;if(side==0){Note("no_crossing");return;}
            string signal=side==1?"L":"S";
            Print(string.Format(CultureInfo.InvariantCulture,"SIGNAL {0:yyyy-MM-ddTHH:mm:ss} side={1} close={2:R} mean={3:R} lower={4:R} upper={5:R}",end,signal,Close[0],bands[0],bands[1],bands[2]));
            SetStopLoss(signal,CalculationMode.Ticks,48,false);pending=true;entries++;Note("entry_submitted");
            if(side==1)EnterLong(1,signal);else EnterShort(1,signal);
        }
        protected override void OnOrderUpdate(Order order,double limitPrice,double stopPrice,int quantity,int filled,double averageFillPrice,OrderState orderState,DateTime time,ErrorCode error,string comment)
        {
            if((order.Name=="L"||order.Name=="S")&&(orderState==OrderState.Filled||orderState==OrderState.Cancelled||orderState==OrderState.Rejected))pending=false;
            if(error!=ErrorCode.NoError)Print("ORDER_ERROR "+error+" "+comment);
        }
        protected override void OnExecutionUpdate(Execution execution,string executionId,double price,int quantity,MarketPosition marketPosition,string orderId,DateTime time)
        {if(execution.Order!=null && (execution.Order.Name=="L"||execution.Order.Name=="S") && marketPosition!=MarketPosition.Flat)entryBar=CurrentBar;}
    }
}
