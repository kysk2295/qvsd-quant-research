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
    // BEGIN PURE GAP MATH
    public static class CodexGapMath
    {
        public static DateTime PreviousWeekday(DateTime day)
        {
            day=day.Date.AddDays(-1);
            while(day.DayOfWeek==DayOfWeek.Saturday || day.DayOfWeek==DayOfWeek.Sunday)day=day.AddDays(-1);
            return day;
        }
        public static double Sigma(double[] values)
        {
            if(values.Length!=60)throw new InvalidOperationException("Exactly60 prior closes required");
            double mean=0,sum=0;
            foreach(double value in values)mean+=value/60.0;
            foreach(double value in values)sum+=(value-mean)*(value-mean);
            return Math.Sqrt(sum/60.0);
        }
        public static bool Qualifies(double open,double close,double sigma,int multiples)
        { return open>0 && close>0 && sigma>0 && !double.IsNaN(sigma) && !double.IsInfinity(sigma) && open-close < -multiples*sigma; }
    }
    // END PURE GAP MATH

    public class CodexGapFade : Strategy
    {
        [NinjaScriptProperty,Range(3,3)] public int GapSigma {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private TimeZoneInfo eastern;
        private DateTime day=DateTime.MinValue,previous=DateTime.MinValue,priorDate=DateTime.MinValue;
        private double priorClose,priorSigma;
        private bool priorValid,gap,reported,attempted;
        private int count,entries;
        private readonly Queue<double> closes=new Queue<double>();
        private readonly Dictionary<string,int> counts=new Dictionary<string,int>();
        private void Note(string reason){if(!counts.ContainsKey(reason))counts[reason]=0;counts[reason]++;}
        protected override void OnStateChange()
        {
            if(State==State.SetDefaults)
            {
                Name="CodexGapFade";GapSigma=3;FirstDate=20261007;LastDate=20261022;
                Calculate=Calculate.OnBarClose;BarsRequiredToTrade=1;EntriesPerDirection=1;
                IsExitOnSessionCloseStrategy=true;IsInstantiatedOnEachOptimizationIteration=true;
            }
            else if(State==State.DataLoaded)
            {
                eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute || BarsPeriod.Value!=1)
                    throw new InvalidOperationException("Requires one-minute bars");
            }
        }
        protected override void OnBarUpdate()
        {
            if(State!=State.Historical || Account==null || Account.Name!=Account.BackTestAccountName)return;
            if(Instrument.MasterInstrument.Name!="NQ")throw new InvalidOperationException("NQ only");
            DateTime end=TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(Time[0],DateTimeKind.Unspecified),Core.Globals.GeneralOptions.TimeZoneInfo,eastern);
            DateTime start=end.AddMinutes(-1);
            if(day!=start.Date)
            {day=start.Date;previous=DateTime.MinValue;count=entries=0;gap=reported=attempted=false;closes.Clear();counts.Clear();}
            int date=day.Year*10000+day.Month*100+day.Day,m=start.Hour*60+start.Minute;
            bool evaluate=date>=FirstDate && date<=LastDate;
            if(m<570 || m>=960)return;
            if((count==0 && m!=570)||(previous!=DateTime.MinValue && start!=previous.AddMinutes(1)))gap=true;
            previous=start;count++;
            // Preserve prior context until this session is complete; never use today's volatility for today's gap.
            if(evaluate && m==570 && !attempted)
            {
                attempted=true;
                bool ready=priorValid && priorDate==CodexGapMath.PreviousWeekday(day) && !gap;
                bool qualified=ready && CodexGapMath.Qualifies(Open[0],priorClose,priorSigma,GapSigma);
                Print(string.Format(CultureInfo.InvariantCulture,"GAP {0:yyyyMMdd} priorDate={1:yyyyMMdd} priorClose={2:R} open={3:R} sigma={4:R} ready={5} qualified={6}",day,priorDate,priorClose,Open[0],priorSigma,ready,qualified));
                if(!ready)Note("missing_previous_context");
                else if(priorSigma<=0)Note("zero_sigma");
                else if(!qualified)Note("gap_threshold_not_met");
                else if(Position.MarketPosition!=MarketPosition.Flat)Note("position_not_flat");
                else
                {
                    SetStopLoss("L",CalculationMode.Ticks,48,false);entries++;Note("entry_submitted");
                    Print(string.Format(CultureInfo.InvariantCulture,"SIGNAL {0:yyyy-MM-ddTHH:mm:ss} side=L delta={1:R} sigma={2:R}",end,Open[0]-priorClose,priorSigma));
                    EnterLong(1,"L");
                }
            }
            if(evaluate && Position.MarketPosition==MarketPosition.Long && end.TimeOfDay>=new TimeSpan(10,15,0))
            {ExitLong("TimeExit","L");Note("exit_submitted");}
            closes.Enqueue(Close[0]);if(closes.Count>60)closes.Dequeue();
            if(end.TimeOfDay==new TimeSpan(16,0,0) && !reported)
            {
                priorDate=day;priorClose=Close[0];priorValid=count==390 && !gap && closes.Count==60;
                priorSigma=priorValid?CodexGapMath.Sigma(closes.ToArray()):0;
                Print(string.Format(CultureInfo.InvariantCulture,"CONTEXT {0:yyyyMMdd} bars={1} gap={2} close={3:R} sigma={4:R} valid={5}",day,count,gap,priorClose,priorSigma,priorValid));
                if(evaluate)
                {Print("AUDIT "+date+" bars="+count+" gap="+gap+" entries="+entries);Print("COUNTS "+date+" "+string.Join(" ",counts.OrderBy(x=>x.Key).Select(x=>x.Key+"="+x.Value)));}
                reported=true;
            }
        }
        protected override void OnOrderUpdate(Order order,double limitPrice,double stopPrice,int quantity,int filled,double averageFillPrice,OrderState orderState,DateTime time,ErrorCode error,string comment)
        {if(error!=ErrorCode.NoError)Print("ORDER_ERROR "+error+" "+comment);}
    }
}
