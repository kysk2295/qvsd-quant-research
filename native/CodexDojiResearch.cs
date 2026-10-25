using System;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
namespace NinjaTrader.NinjaScript.Strategies
{
    public class CodexDojiResearch : Strategy
    {
        [NinjaScriptProperty,Range(0,60)] public int SessionWindow {get;set;}
        [NinjaScriptProperty,Range(0.6,1.0)] public double TargetRatio {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private TimeZoneInfo eastern;
        private DateTime day=DateTime.MinValue,previous=DateTime.MinValue;
        private int count,signals,rejected,entries,entryBar=-1,dayTradeStart;
        private double dayProfit;
        private bool gap,pending;
        protected override void OnStateChange()
        {
            if(State==State.SetDefaults)
            {
                Name="CodexDojiResearch";SessionWindow=0;TargetRatio=.6;FirstDate=20260929;LastDate=20261006;
                Calculate=Calculate.OnBarClose;BarsRequiredToTrade=10;EntriesPerDirection=1;
                IsExitOnSessionCloseStrategy=true;IsInstantiatedOnEachOptimizationIteration=true;
            }
            else if(State==State.DataLoaded)
            {
                eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute || BarsPeriod.Value!=1)throw new InvalidOperationException("1minute only");
            }
        }
        protected override void OnBarUpdate()
        {
            if(State!=State.Historical || Account==null || Account.Name!=Account.BackTestAccountName)return;
            if(Instrument.MasterInstrument.Name!="NQ")throw new InvalidOperationException("NQ only");
            DateTime end=TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(Time[0],DateTimeKind.Unspecified),Core.Globals.GeneralOptions.TimeZoneInfo,eastern);
            DateTime start=end.AddMinutes(-1);int date=start.Year*10000+start.Month*100+start.Day;
            if(date<FirstDate || date>LastDate)return;
            if(start.Date!=day)
            {
                day=start.Date;count=signals=rejected=entries=0;gap=pending=false;entryBar=-1;previous=DateTime.MinValue;
                dayProfit=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;dayTradeStart=SystemPerformance.AllTrades.Count;
            }
            int minute=start.Hour*60+start.Minute;if(minute<570 || minute>=960)return;
            if((count==0&&minute!=570)||(previous!=DateTime.MinValue&&start!=previous.AddMinutes(1)))gap=true;
            previous=start;count++;
            if(Position.MarketPosition==MarketPosition.Long && ((entryBar>=0&&CurrentBar-entryBar>=10)||end.TimeOfDay>=new TimeSpan(15,55,0)))ExitLong("TimeExit","L");
            if(minute==959)Print("AUDIT "+date+" bars="+count+" gap="+gap+" signals="+signals+" rejected="+rejected+" entries="+entries);
            if(gap||count<=10||minute>=945||pending||Position.MarketPosition!=MarketPosition.Flat||entries>=(SessionWindow==0?4:1))return;
            if(SessionWindow!=0 && minute>=570+SessionWindow)return;
            double daily=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit-dayProfit-10*(SystemPerformance.AllTrades.Count-dayTradeStart);
            if(daily<=-900)return;
            double average=0;for(int i=1;i<=10;i++)average+=High[i]-Low[i];average/=10;
            if(Close[1]>=Open[1]||Math.Abs(Close[0]-Open[0])>.1*average)return;
            signals++;
            double stop=Low[0]-TickSize, distance=Close[0]-stop, risk=(distance+2)*20+10;
            int targetTicks=(int)Math.Floor(TargetRatio*(Open[1]-Close[1])/TickSize);
            if(distance<TickSize||risk>300||targetTicks<2){rejected++;Print("CONDITION_REJECT "+date+" risk="+risk+" targetTicks="+targetTicks);return;}
            SetStopLoss("L",CalculationMode.Price,stop,false);
            SetProfitTarget("L",CalculationMode.Ticks,targetTicks);
            pending=true;entries++;EnterLong(1,"L");
        }
        protected override void OnExecutionUpdate(Execution execution,string executionId,double price,int quantity,MarketPosition marketPosition,string orderId,DateTime time)
        {if(execution.Order!=null && execution.Order.Name=="L"){entryBar=CurrentBar;pending=false;}}
        protected override void OnOrderUpdate(Order order,double limitPrice,double stopPrice,int quantity,int filled,double averageFillPrice,OrderState orderState,DateTime time,ErrorCode error,string comment)
        {
            if(order.Name=="L"&&(orderState==OrderState.Rejected||orderState==OrderState.Cancelled))pending=false;
            if(error!=ErrorCode.NoError)Print("ORDER_ERROR "+error+" "+comment);
        }
    }
}
