using System;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Strategies
{
    // Data-only collector: no entry, exit or order submission methods.
    public class CodexRthDataAudit : Strategy
    {
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private TimeZoneInfo eastern;
        protected override void OnStateChange()
        {
            if(State==State.SetDefaults){Name="CodexRthDataAudit";FirstDate=20260928;LastDate=20261001;Calculate=Calculate.OnBarClose;BarsRequiredToTrade=1;IsInstantiatedOnEachOptimizationIteration=true;}
            else if(State==State.DataLoaded){if(Account==null||Account.Name!=Account.BackTestAccountName)throw new InvalidOperationException("Backtest only");if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute||BarsPeriod.Value!=1)throw new InvalidOperationException("Minute1 only");eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");}
        }
        protected override void OnBarUpdate()
        {
            if(State!=State.Historical||Account==null||Account.Name!=Account.BackTestAccountName)return;
            if(Instrument.MasterInstrument.Name!="NQ")throw new InvalidOperationException("NQ only");
            DateTime end=TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(Time[0],DateTimeKind.Unspecified),Core.Globals.GeneralOptions.TimeZoneInfo,eastern),start=end.AddMinutes(-1);
            int date=start.Year*10000+start.Month*100+start.Day;
            if(date<FirstDate||date>LastDate||start.TimeOfDay<new TimeSpan(9,30,0)||start.TimeOfDay>=new TimeSpan(16,0,0))return;
            Print(string.Format(CultureInfo.InvariantCulture,"RTH_BAR|{0:yyyy-MM-ddTHH:mm:ss}|{1:R}|{2:R}|{3:R}|{4:R}|{5}",end,Open[0],High[0],Low[0],Close[0],Volume[0]));
        }
    }
}
