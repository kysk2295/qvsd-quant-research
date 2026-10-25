using System;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Strategies
{
    // Independently implemented research adaptation of the public QC Boot Camp ORB rule.
    // Source and deliberate differences are documented in docs/orb-research-batch.md.
    public class CodexPublicORB : Strategy
    {
        [NinjaScriptProperty, Range(1,120)]
        public int RangeMinutes {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private TimeZoneInfo eastern;
        private DateTime day=DateTime.MinValue, previous=DateTime.MinValue;
        private double high,low;
        private int rangeCount,sessionCount;
        private bool entered, gap, reported;
        protected override void OnStateChange()
        {
            if(State==State.SetDefaults)
            {
                Name="CodexPublicORB"; RangeMinutes=30; FirstDate=20260928; LastDate=20261006;
                Calculate=Calculate.OnBarClose; BarsRequiredToTrade=0;
                EntriesPerDirection=1; IsExitOnSessionCloseStrategy=true;
                IsInstantiatedOnEachOptimizationIteration=true;
            }
            else if(State==State.DataLoaded)
            {
                eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute || BarsPeriod.Value!=1)
                    throw new InvalidOperationException("Requires 1-minute bars.");
            }
        }
        protected override void OnBarUpdate()
        {
            if(State!=State.Historical || Account==null || Account.Name!=Account.BackTestAccountName) return;
            if(Instrument.MasterInstrument.Name!="NQ") throw new InvalidOperationException("NQ only");
            DateTime end=TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(Time[0],DateTimeKind.Unspecified),
                Core.Globals.GeneralOptions.TimeZoneInfo,eastern);
            DateTime start=end.AddMinutes(-1);
            if(start.Date!=day)
            {
                day=start.Date; high=double.MinValue; low=double.MaxValue;
                rangeCount=sessionCount=0; entered=gap=reported=false; previous=DateTime.MinValue;
            }
            int date=day.Year*10000+day.Month*100+day.Day;
            if(date<FirstDate || date>LastDate) return;
            int minute=start.Hour*60+start.Minute;
            if(minute<570 || minute>810) return;
            if(previous!=DateTime.MinValue && start!=previous.AddMinutes(1)) gap=true;
            previous=start; sessionCount++;
            if(minute<570+RangeMinutes)
            {high=Math.Max(high,High[0]);low=Math.Min(low,Low[0]);rangeCount++;return;}
            // Submit at 13:29 bar close (13:30); native historical next-bar execution.
            if(end.TimeOfDay>=new TimeSpan(13,30,0))
            {
                if(Position.MarketPosition==MarketPosition.Long) ExitLong("TimeExit","L");
                if(Position.MarketPosition==MarketPosition.Short) ExitShort("TimeExit","S");
                if(!reported) {Print("AUDIT "+date+" range="+rangeCount+" bars="+sessionCount+" gap="+gap);reported=true;}
                return;
            }
            if(entered || gap || rangeCount!=RangeMinutes || Position.MarketPosition!=MarketPosition.Flat) return;
            if(Close[0]>high) {entered=true;Print("SIGNAL "+end.ToString("o")+" L "+high);EnterLong(1,"L");}
            else if(Close[0]<low) {entered=true;Print("SIGNAL "+end.ToString("o")+" S "+low);EnterShort(1,"S");}
        }
    }
}

