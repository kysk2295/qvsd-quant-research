using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;

namespace NinjaTrader.NinjaScript.Strategies
{
    // BEGIN PURE SETUP STATE: tested directly without NinjaTrader or market access.
    public sealed class CodexMomentumSetupState
    {
        public int Side { get; private set; }
        public int ArmedBar { get; private set; }
        public int SignalAge { get; private set; }
        public string Event { get; private set; }
        public void Clear() { Side=0; ArmedBar=-1; }
        public int Step(int bias,double k,double histogram,double previousHistogram,int bar,int maxAge)
        {
            Event="no_setup"; SignalAge=0;
            if(Side!=0)
            {
                int age=bar-ArmedBar;
                if(bias!=Side) { Clear(); Event="setup_bias_invalidated"; return 0; }
                if(age>maxAge) { Clear(); Event="setup_expired"; return 0; }
                bool crossed=Side==1 ? previousHistogram<=0 && histogram>0 : previousHistogram>=0 && histogram<0;
                if(age>=1 && crossed)
                {
                    int result=Side; SignalAge=age; Clear(); Event="confirmation"; return result;
                }
                Event="await_confirmation"; return 0;
            }
            if((bias==1 && k<20)||(bias==-1 && k>80))
            { Side=bias; ArmedBar=bar; Event="setup_armed"; }
            return 0;
        }
    }
    // END PURE SETUP STATE

    // Historical-only intraday adaptation of ChartSchool Moving Momentum.
    public class CodexMovingMomentum : Strategy
    {
        [NinjaScriptProperty,Range(6,6)] public int SetupMaxBars {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private TimeZoneInfo eastern;
        private DateTime day=DateTime.MinValue,previous=DateTime.MinValue;
        private bool gap,pending,reported;
        private int count,entries,entryBar=-1,startTrades;
        private double startProfit;
        private readonly CodexMomentumSetupState setup=new CodexMomentumSetupState();
        private readonly Dictionary<string,int> counts=new Dictionary<string,int>();
        private void Note(string reason) { if(!counts.ContainsKey(reason))counts[reason]=0; counts[reason]++; }
        protected override void OnStateChange()
        {
            if(State==State.SetDefaults)
            {
                Name="CodexMovingMomentum"; SetupMaxBars=6; FirstDate=20261007; LastDate=20261022;
                Calculate=Calculate.OnBarClose; BarsRequiredToTrade=1; EntriesPerDirection=1;
                IsExitOnSessionCloseStrategy=true; IsInstantiatedOnEachOptimizationIteration=true;
            }
            else if(State==State.DataLoaded)
            {
                eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute || BarsPeriod.Value!=5)
                    throw new InvalidOperationException("Requires five-minute bars");
                SMA(20); SMA(150); Stochastics(3,14,3); MACD(12,26,9);
            }
        }
        protected override void OnBarUpdate()
        {
            if(State!=State.Historical || Account==null || Account.Name!=Account.BackTestAccountName)return;
            if(Instrument.MasterInstrument.Name!="NQ")throw new InvalidOperationException("NQ only");
            // Read on every ETH bar so indicator history is continuously updated.
            double fast=SMA(20)[0],slow=SMA(150)[0],k=Stochastics(3,14,3).K[0],hist=MACD(12,26,9).Diff[0];
            DateTime end=TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(Time[0],DateTimeKind.Unspecified),Core.Globals.GeneralOptions.TimeZoneInfo,eastern);
            DateTime start=end.AddMinutes(-5);
            if(day!=start.Date)
            {
                day=start.Date;previous=DateTime.MinValue;count=entries=0;gap=pending=reported=false;counts.Clear();setup.Clear();
                startProfit=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;startTrades=SystemPerformance.AllTrades.Count;
            }
            int date=day.Year*10000+day.Month*100+day.Day,m=start.Hour*60+start.Minute;
            if(date<FirstDate || date>LastDate || m<570 || m>=960) { setup.Clear(); return; }
            if((count==0 && m!=570)||(previous!=DateTime.MinValue && start!=previous.AddMinutes(5)))gap=true;
            previous=start;count++;
            bool timed=(entryBar>=0 && CurrentBar-entryBar>=10)||end.TimeOfDay>=new TimeSpan(15,55,0);
            if(Position.MarketPosition==MarketPosition.Long && (timed || hist<0))
            { ExitLong("Exit","L");Note("exit_submitted"); }
            if(Position.MarketPosition==MarketPosition.Short && (timed || hist>0))
            { ExitShort("Exit","S");Note("exit_submitted"); }
            if(end.TimeOfDay>=new TimeSpan(16,0,0) && !reported)
            { Print("AUDIT "+date+" bars="+count+" gap="+gap+" entries="+entries);Print("COUNTS "+date+" "+string.Join(" ",counts.OrderBy(x=>x.Key).Select(x=>x.Key+"="+x.Value)));reported=true; }
            if(CurrentBar<200) { setup.Clear();Note("indicator_warmup");return; }
            if(gap) { setup.Clear();Note("session_gap");return; }
            if(m<580 || m>=930) { setup.Clear();Note("entry_time_filter");return; }
            if(pending || Position.MarketPosition!=MarketPosition.Flat) { setup.Clear();Note("position_or_pending");return; }
            if(entries>=4) { setup.Clear();Note("entry_limit");return; }
            double realized=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit-startProfit-10*(SystemPerformance.AllTrades.Count-startTrades);
            if(realized<=-900) { setup.Clear();Note("daily_loss_limit");return; }
            int bias=fast>slow?1:fast<slow?-1:0;
            double prior=MACD(12,26,9).Diff[1];
            int side=setup.Step(bias,k,hist,prior,CurrentBar,SetupMaxBars); Note(setup.Event);
            Print(string.Format(CultureInfo.InvariantCulture,"TRACE {0:yyyy-MM-ddTHH:mm:ss} bar={1} bias={2} k={3:R} hist={4:R} prior={5:R} event={6} age={7}",end,CurrentBar,bias,k,hist,prior,setup.Event,setup.SignalAge));
            if(side==0)return;
            string signal=side==1?"L":"S";
            Print(string.Format(CultureInfo.InvariantCulture,"SIGNAL {0:yyyy-MM-ddTHH:mm:ss} side={1} age={2}",end,signal,setup.SignalAge));
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
        { if(execution.Order!=null && (execution.Order.Name=="L"||execution.Order.Name=="S") && marketPosition!=MarketPosition.Flat)entryBar=CurrentBar; }
    }
}
