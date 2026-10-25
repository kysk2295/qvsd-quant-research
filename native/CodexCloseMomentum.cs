using System;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
namespace NinjaTrader.NinjaScript.Strategies
{
    // Independent NQ adaptation of QC Intraday ETF Momentum. Not ETF return replication.
    public class CodexCloseMomentum : Strategy
    {
        [NinjaScriptProperty,Range(0,1)] public int Anchor {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private TimeZoneInfo eastern;
        private DateTime day=DateTime.MinValue,prev=DateTime.MinValue,closeDay=DateTime.MinValue;
        private double previousClose,opening,signal;
        private int count;
        private bool gap,entered,ready;
        protected override void OnStateChange()
        {
            if(State==State.SetDefaults) {
                Name="CodexCloseMomentum"; Anchor=0; FirstDate=20260929; LastDate=20261006;
                Calculate=Calculate.OnBarClose; BarsRequiredToTrade=0; EntriesPerDirection=1;
                IsExitOnSessionCloseStrategy=true; IsInstantiatedOnEachOptimizationIteration=true;
            } else if(State==State.DataLoaded) {
                eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute || BarsPeriod.Value!=1)
                    throw new InvalidOperationException("1-minute bars only");
            }
        }
        protected override void OnBarUpdate()
        {
            if(State!=State.Historical || Account==null || Account.Name!=Account.BackTestAccountName) return;
            if(Instrument.MasterInstrument.Name!="NQ") throw new InvalidOperationException("NQ only");
            DateTime end=TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(Time[0],DateTimeKind.Unspecified),Core.Globals.GeneralOptions.TimeZoneInfo,eastern);
            DateTime start=end.AddMinutes(-1);
            if(start.Date!=day) {day=start.Date;prev=DateTime.MinValue;count=0;gap=entered=ready=false;signal=0;}
            int m=start.Hour*60+start.Minute;
            if(m<570 || m>960)return;
            if(m==570)opening=Open[0];
            if(prev==DateTime.MinValue && m!=570)gap=true;
            if(prev!=DateTime.MinValue && start!=prev.AddMinutes(1))gap=true;
            prev=start;count++;
            if(m==599 && count==30 && !gap) {
                DateTime expected=day.AddDays(-1);while(expected.DayOfWeek==DayOfWeek.Saturday || expected.DayOfWeek==DayOfWeek.Sunday)expected=expected.AddDays(-1);
                ready=Anchor==1 || closeDay==expected;
                if(ready)signal=Close[0]-(Anchor==0?previousClose:opening);
            }
            int date=day.Year*10000+day.Month*100+day.Day;
            bool evaluation=date>=FirstDate && date<=LastDate;
            if(evaluation && end.Hour==15 && end.Minute==30 && ready && !gap && count==360 && !entered) {
                entered=true;Print("SIGNAL "+date+" anchor="+Anchor+" delta="+signal);
                if(signal>0)EnterLong(1,"L");else if(signal<0)EnterShort(1,"S");
            }
            if(end.Hour==16 && end.Minute==0) {
                if(Position.MarketPosition==MarketPosition.Long)ExitLong("TimeExit","L");
                if(Position.MarketPosition==MarketPosition.Short)ExitShort("TimeExit","S");
                if(evaluation)Print("AUDIT "+date+" bars="+count+" gap="+gap+" ready="+ready);
                if(count==390 && !gap){previousClose=Close[0];closeDay=day;}
            }
        }
    }
}

