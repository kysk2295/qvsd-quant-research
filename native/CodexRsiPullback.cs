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
    // NQ intraday research adaptation of ChartSchool RSI(2), not a daily-rule replication.
    public class CodexRsiPullback : Strategy
    {
        [NinjaScriptProperty,Range(2,5)] public int EntryLevel {get;set;}
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
                Name="CodexRsiPullback";EntryLevel=5;FirstDate=20260929;LastDate=20261006;
                Calculate=Calculate.OnBarClose;BarsRequiredToTrade=1;EntriesPerDirection=1;
                IsExitOnSessionCloseStrategy=true;IsInstantiatedOnEachOptimizationIteration=true;
            }
            else if(State==State.DataLoaded)
            {
                eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute || BarsPeriod.Value!=5)
                    throw new InvalidOperationException("Requires five-minute bars");
                // Instantiate indicators before the first possible entry.
                RSI(2,1);SMA(200);SMA(5);
            }
        }
        protected override void OnBarUpdate()
        {
            if(State!=State.Historical || Account==null || Account.Name!=Account.BackTestAccountName)return;
            if(Instrument.MasterInstrument.Name!="NQ")throw new InvalidOperationException("NQ only");
            // Update indicators across all supplied ETH bars; entry remains RTH-only.
            double rsi=RSI(2,1)[0],trend=SMA(200)[0],exit=SMA(5)[0];
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
            if(Position.MarketPosition==MarketPosition.Long &&
               (Close[0]>exit || (entryBar>=0 && CurrentBar-entryBar>=10) || end.TimeOfDay>=new TimeSpan(15,55,0)))
            {ExitLong("Exit","L");Note("exit_submitted");}
            if(end.TimeOfDay>=new TimeSpan(16,0,0) && !reported)
            {Print("AUDIT "+date+" bars="+count+" gap="+gap+" entries="+entries);Print("COUNTS "+date+" "+string.Join(" ",counts.OrderBy(x=>x.Key).Select(x=>x.Key+"="+x.Value)));reported=true;}
            if(CurrentBar<200){Note("indicator_warmup");return;}
            if(gap){Note("session_gap");return;}
            if(m<580 || m>=930){Note("entry_time_filter");return;}
            if(pending || Position.MarketPosition!=MarketPosition.Flat){Note("position_or_pending");return;}
            if(entries>=4){Note("entry_limit");return;}
            double realized=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit-startProfit-10*(SystemPerformance.AllTrades.Count-startTrades);
            if(realized<=-900){Note("daily_loss_limit");return;}
            if(Close[0]<=trend){Note("trend_filter");return;}
            if(rsi>=EntryLevel){Note("rsi_filter");return;}
            // 12-point stop + two-point allowance + $10 assumed fee = $290 estimate.
            SetStopLoss("L",CalculationMode.Ticks,48,false);
            pending=true;entries++;Note("entry_submitted");EnterLong(1,"L");
        }
        protected override void OnOrderUpdate(Order order,double limitPrice,double stopPrice,int quantity,int filled,double averageFillPrice,OrderState orderState,DateTime time,ErrorCode error,string comment)
        {
            if(order.Name=="L"&&(orderState==OrderState.Filled||orderState==OrderState.Cancelled||orderState==OrderState.Rejected))pending=false;
            if(error!=ErrorCode.NoError)Print("ORDER_ERROR "+error+" "+comment);
        }
        protected override void OnExecutionUpdate(Execution execution,string executionId,double price,int quantity,MarketPosition marketPosition,string orderId,DateTime time)
        {if(execution.Order!=null && execution.Order.Name=="L" && marketPosition==MarketPosition.Long)entryBar=CurrentBar;}
    }
}
