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
    // BEGIN PURE NR7 MATH
    public static class CodexNr7Math
    {
        public static bool Qualifies(double[] ranges)
        {
            if(ranges.Length!=7)return false;
            if(ranges.Any(x=>x<=0||double.IsNaN(x)||double.IsInfinity(x)))return false;
            return ranges.Take(6).All(x=>ranges[6]<x);
        }
        public static int Breakout(double close,double high,double low)
        {return close>=high+0.25?1:close<=low-0.25?-1:0;}
        public static DateTime PreviousWeekday(DateTime date)
        {date=date.Date.AddDays(-1);while(date.DayOfWeek==DayOfWeek.Saturday||date.DayOfWeek==DayOfWeek.Sunday)date=date.AddDays(-1);return date;}
    }
    // END PURE NR7 MATH

    public class CodexNr7Rth : Strategy
    {
        [NinjaScriptProperty,Range(7,7)] public int LookbackDays {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private sealed class Session {public DateTime Date;public double High,Low;}
        private readonly Queue<Session> sessions=new Queue<Session>();
        private readonly Dictionary<string,int> counts=new Dictionary<string,int>();
        private TimeZoneInfo eastern;
        private DateTime day=DateTime.MinValue,previous=DateTime.MinValue;
        private int count,entries;
        private double high,low,priorHigh,priorLow;
        private bool gap,reported,qualified;
        private void Note(string reason){if(!counts.ContainsKey(reason))counts[reason]=0;counts[reason]++;}
        protected override void OnStateChange()
        {
            if(State==State.SetDefaults){Name="CodexNr7Rth";LookbackDays=7;FirstDate=20261013;LastDate=20261022;Calculate=Calculate.OnBarClose;BarsRequiredToTrade=1;EntriesPerDirection=1;IsExitOnSessionCloseStrategy=true;IsInstantiatedOnEachOptimizationIteration=true;}
            else if(State==State.DataLoaded){if(Account==null||Account.Name!=Account.BackTestAccountName)throw new InvalidOperationException("Backtest only");if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute||BarsPeriod.Value!=1)throw new InvalidOperationException("Minute1 required");eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");}
        }
        protected override void OnBarUpdate()
        {
            if(State!=State.Historical||Account==null||Account.Name!=Account.BackTestAccountName)return;
            if(Instrument.MasterInstrument.Name!="NQ")throw new InvalidOperationException("NQ only");
            DateTime end=TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(Time[0],DateTimeKind.Unspecified),Core.Globals.GeneralOptions.TimeZoneInfo,eastern),start=end.AddMinutes(-1);
            int date=start.Year*10000+start.Month*100+start.Day;
            if(date<20261002||date>LastDate||start.TimeOfDay<new TimeSpan(9,30,0)||start.TimeOfDay>=new TimeSpan(16,0,0))return;
            bool evaluate=date>=FirstDate;
            if(day!=start.Date)
            {
                day=start.Date;count=entries=0;previous=DateTime.MinValue;gap=reported=false;counts.Clear();high=double.MinValue;low=double.MaxValue;
                if(sessions.Count>0&&sessions.Last().Date!=CodexNr7Math.PreviousWeekday(day))sessions.Clear();
                var list=sessions.ToArray();qualified=list.Length==7&&CodexNr7Math.Qualifies(list.Select(x=>x.High-x.Low).ToArray());
                priorHigh=list.Length>0?list.Last().High:0;priorLow=list.Length>0?list.Last().Low:0;
                if(evaluate)Print(string.Format(CultureInfo.InvariantCulture,"SETUP {0:yyyyMMdd} priorCount={1} qualified={2} priorDate={3:yyyyMMdd} high={4:R} low={5:R}",day,list.Length,qualified,list.Length>0?list.Last().Date:DateTime.MinValue,priorHigh,priorLow));
            }
            if((count==0&&start.TimeOfDay!=new TimeSpan(9,30,0))||(previous!=DateTime.MinValue&&start!=previous.AddMinutes(1)))gap=true;
            previous=start;count++;high=Math.Max(high,High[0]);low=Math.Min(low,Low[0]);
            if(evaluate&&end.TimeOfDay>=new TimeSpan(15,55,0))
            {if(Position.MarketPosition==MarketPosition.Long)ExitLong("SessionExit","L");if(Position.MarketPosition==MarketPosition.Short)ExitShort("SessionExit","S");}
            if(end.TimeOfDay==new TimeSpan(16,0,0)&&!reported)
            {
                bool valid=count==390&&!gap;
                Print(string.Format(CultureInfo.InvariantCulture,"DAY {0:yyyyMMdd} bars={1} gap={2} high={3:R} low={4:R} close={5:R} valid={6}",day,count,gap,high,low,Close[0],valid));
                if(valid){sessions.Enqueue(new Session{Date=day,High=high,Low=low});if(sessions.Count>7)sessions.Dequeue();}else sessions.Clear();
                if(evaluate){Print("AUDIT "+date+" bars="+count+" gap="+gap+" entries="+entries);Print("COUNTS "+date+" "+string.Join(" ",counts.OrderBy(x=>x.Key).Select(x=>x.Key+"="+x.Value)));}
                foreach(Trade t in SystemPerformance.AllTrades)Print("CLOCK_TRADE|"+t.Entry.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+t.Entry.Time.Ticks+"|"+t.Exit.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+t.Exit.Time.Ticks);
                reported=true;
            }
            if(!evaluate)return;
            if(gap){Note("session_gap");return;}
            if(!qualified){Note("not_daily_nr7");return;}
            if(end.TimeOfDay<new TimeSpan(9,31,0)||end.TimeOfDay>new TimeSpan(15,25,0)){Note("entry_time_filter");return;}
            if(entries>=1||Position.MarketPosition!=MarketPosition.Flat){Note("entry_or_position_limit");return;}
            int side=CodexNr7Math.Breakout(Close[0],priorHigh,priorLow);if(side==0){Note("inside_prior_day");return;}
            string signal=side>0?"L":"S";entries++;Note("entry_submitted");
            Print(string.Format(CultureInfo.InvariantCulture,"SIGNAL {0:yyyy-MM-ddTHH:mm:ss} side={1} close={2:R} high={3:R} low={4:R}",end,signal,Close[0],priorHigh,priorLow));
            SetStopLoss(signal,CalculationMode.Ticks,48,false);if(side>0)EnterLong(1,signal);else EnterShort(1,signal);
        }
        protected override void OnOrderUpdate(Order order,double limitPrice,double stopPrice,int quantity,int filled,double averageFillPrice,OrderState orderState,DateTime time,ErrorCode error,string comment)
        {if(error!=ErrorCode.NoError)Print("ORDER_ERROR "+error+" "+comment);}
        protected override void OnExecutionUpdate(Execution execution,string executionId,double price,int quantity,MarketPosition marketPosition,string orderId,DateTime time)
        {Print("CLOCK_EXEC|"+execution.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+execution.Time.Ticks+"|"+time.ToString("o",CultureInfo.InvariantCulture)+"|"+time.Ticks+"|"+Time[0].ToString("o",CultureInfo.InvariantCulture)+"|"+execution.Order.Name+"|"+price.ToString("R",CultureInfo.InvariantCulture)+"|"+quantity+"|"+State);}
    }
}
