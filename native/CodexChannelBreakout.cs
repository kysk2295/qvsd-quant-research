using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;

namespace NinjaTrader.NinjaScript.Strategies
{
    // NQ RTH close-confirmed adaptation of TradingView Channel BreakOut; not an exact stop-entry port.
    public class CodexChannelBreakout : Strategy
    {
        [NinjaScriptProperty,Range(5,20)] public int ChannelLength {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private TimeZoneInfo eastern;
        private DateTime day=DateTime.MinValue,previous=DateTime.MinValue;
        private bool gap,pending,reported;
        private int count,entries,entryBar=-1,startTrades;
        private double startProfit;
        private readonly Dictionary<string,int> counts=new Dictionary<string,int>();
        private void Note(string reason){if(!counts.ContainsKey(reason)) counts[reason]=0;counts[reason]++;}
        protected override void OnStateChange()
        {
            if(State==State.SetDefaults)
            {
                Name="CodexChannelBreakout";ChannelLength=5;FirstDate=20260929;LastDate=20261006;
                Calculate=Calculate.OnBarClose;BarsRequiredToTrade=1;EntriesPerDirection=1;
                IsExitOnSessionCloseStrategy=true;IsInstantiatedOnEachOptimizationIteration=true;
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
            if(State!=State.Historical || Account==null || Account.Name!=Account.BackTestAccountName)return;
            if(Instrument.MasterInstrument.Name!="NQ")throw new InvalidOperationException("NQ only");

            DateTime end=TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(Time[0],DateTimeKind.Unspecified),Core.Globals.GeneralOptions.TimeZoneInfo,eastern);
            DateTime start=end.AddMinutes(-5);
            if(day!=start.Date)
            {
                day=start.Date;previous=DateTime.MinValue;count=entries=0;gap=pending=reported=false;counts.Clear();
                startProfit=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;startTrades=SystemPerformance.AllTrades.Count;
            }
            int date=day.Year*10000+day.Month*100+day.Day,m=start.Hour*60+start.Minute;
            if(date<FirstDate || date>LastDate || m<570 || m>=960)return;
            if((count==0 && m!=570)||(previous!=DateTime.MinValue && start!=previous.AddMinutes(5)))gap=true;
            previous=start;count++;
            double upper=double.MinValue,lower=double.MaxValue;
            bool ready=count>ChannelLength && CurrentBar>=ChannelLength;
            if(ready) for(int i=1;i<=ChannelLength;i++){upper=Math.Max(upper,High[i]);lower=Math.Min(lower,Low[i]);}
            bool timed=(entryBar>=0 && CurrentBar-entryBar>=10)||end.TimeOfDay>=new TimeSpan(15,55,0);
            if(Position.MarketPosition==MarketPosition.Long && (timed || (ready && Close[0]<lower)))
            {ExitLong("Exit","L");Note("exit_submitted");}
            if(Position.MarketPosition==MarketPosition.Short && (timed || (ready && Close[0]>upper)))
            {ExitShort("Exit","S");Note("exit_submitted");}
            if(end.TimeOfDay>=new TimeSpan(16,0,0) && !reported)
            {Print("AUDIT "+date+" bars="+count+" gap="+gap+" entries="+entries);Print("COUNTS "+date+" "+string.Join(" ",counts.OrderBy(x=>x.Key).Select(x=>x.Key+"="+x.Value)));reported=true;}
            if(!ready){Note("session_channel_build");return;}
            if(gap){Note("session_gap");return;}
            if(m<580 || m>=930){Note("entry_time_filter");return;}
            if(pending || Position.MarketPosition!=MarketPosition.Flat){Note("position_or_pending");return;}
            if(entries>=4){Note("entry_limit");return;}
            double realized=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit-startProfit-10*(SystemPerformance.AllTrades.Count-startTrades);
            if(realized<=-900){Note("daily_loss_limit");return;}
            int side=Close[0]>upper ? 1:Close[0]<lower ? -1:0;
            if(side==0){Note("no_channel_break");return;}
            string signal=side==1 ? "L":"S";
            // Same fixed $290 pre-entry risk estimate as RSI research, not retuned after results.
            SetStopLoss(signal,CalculationMode.Ticks,48,false);
            pending=true;entries++;Note("entry_submitted");
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
