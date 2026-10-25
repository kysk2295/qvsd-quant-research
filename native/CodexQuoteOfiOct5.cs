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
    // BEGIN PURE OFI GATE
    public static class CodexOfiOct5Gate
    {
        public static int Signal(long now,long featureEnd,long lastSource,bool eligible,double score,double spread,int threshold)
        {
            if(!eligible || featureEnd!=now-60000000000L || lastSource>=featureEnd || lastSource<=0)return 0;
            if(double.IsNaN(score)||double.IsInfinity(score)||double.IsNaN(spread)||spread<=0||spread>4)return 0;
            return score>=threshold?1:score<=-threshold?-1:0;
        }
    }
    // END PURE OFI GATE

    public class CodexQuoteOfiOct5 : Strategy
    {
        [NinjaScriptProperty,Range(10,10)] public int OfiThreshold {get;set;}
        [NinjaScriptProperty] public int FirstDate {get;set;}
        [NinjaScriptProperty] public int LastDate {get;set;}
        private const string FeatureHash="1583b6587ffedd3fd40e95283dc35d473a553577e2b5a8f9af99cd9fb85d55f5";
        private sealed class Feature {public long End,Last;public bool Eligible;public double Score,Spread;}
        private readonly Dictionary<long,Feature> features=new Dictionary<long,Feature>();
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
                Name="CodexQuoteOfiOct5";OfiThreshold=10;FirstDate=20261007;LastDate=20261022;
                Calculate=Calculate.OnBarClose;BarsRequiredToTrade=1;EntriesPerDirection=1;
                IsExitOnSessionCloseStrategy=true;IsInstantiatedOnEachOptimizationIteration=true;
            }
            else if(State==State.DataLoaded)
            {
                if(Account==null || Account.Name!=Account.BackTestAccountName)throw new InvalidOperationException("Backtest account only");
                if(BarsPeriod.BarsPeriodType!=BarsPeriodType.Minute || BarsPeriod.Value!=1)throw new InvalidOperationException("One-minute bars required");
                eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                string path=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),"Codex","qvsd-experiment-runner","data","runner","ofi","oct5-features.csv");
                byte[] bytes=File.ReadAllBytes(path);string hash;
                using(var sha=SHA256.Create())hash=BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
                if(hash!=FeatureHash)throw new InvalidOperationException("Frozen quote feature hash mismatch");
                using(var reader=new StringReader(System.Text.Encoding.ASCII.GetString(bytes)))
                {
                    if(reader.ReadLine()!="end_utc_ns;eligible;ofi;mean_depth;last_source_ns;spread_ticks")throw new InvalidOperationException("Feature schema mismatch");
                    string line;long prior=-1;
                    while((line=reader.ReadLine())!=null)
                    {
                        string[] p=line.Split(';');if(p.Length!=6)throw new InvalidOperationException("Feature field count");
                        long end=long.Parse(p[0],CultureInfo.InvariantCulture),last=long.Parse(p[4],CultureInfo.InvariantCulture);
                        double depth=double.Parse(p[3],CultureInfo.InvariantCulture),ofi=double.Parse(p[2],CultureInfo.InvariantCulture);
                        bool eligible=p[1]=="1";
                        if(end<=prior || last>=end || (eligible && (last<=0 || depth<=0)))throw new InvalidOperationException("Noncausal feature");
                        features.Add(end,new Feature{End=end,Last=last,Eligible=eligible,Score=depth>0?ofi/depth:0,Spread=double.Parse(p[5],CultureInfo.InvariantCulture)});prior=end;
                    }
                }
                Print("FEATURE_HASH "+hash+" rows="+features.Count);
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
            {day=start.Date;previous=DateTime.MinValue;count=entries=0;gap=pending=reported=false;counts.Clear();startProfit=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;startTrades=SystemPerformance.AllTrades.Count;}
            int date=day.Year*10000+day.Month*100+day.Day,m=end.Hour*60+end.Minute;
            if(date<FirstDate || date>LastDate || start.TimeOfDay<new TimeSpan(9,30,0)||start.TimeOfDay>=new TimeSpan(16,0,0))return;
            if((count==0 && start.TimeOfDay!=new TimeSpan(9,30,0))||(previous!=DateTime.MinValue && start!=previous.AddMinutes(1)))gap=true;
            previous=start;count++;
            bool timed=(entryBar>=0 && CurrentBar-entryBar>=5)||m>=955;
            if(Position.MarketPosition==MarketPosition.Long && timed){ExitLong("TimeExit","L");Note("exit_submitted");}
            if(Position.MarketPosition==MarketPosition.Short && timed){ExitShort("TimeExit","S");Note("exit_submitted");}
            if(m>=960 && !reported)
            {foreach(Trade t in SystemPerformance.AllTrades)Print("CLOCK_TRADE|"+t.Entry.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+t.Entry.Time.Ticks+"|"+t.Exit.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+t.Exit.Time.Ticks);
Print("AUDIT "+date+" bars="+count+" gap="+gap+" entries="+entries);Print("COUNTS "+date+" "+string.Join(" ",counts.OrderBy(x=>x.Key).Select(x=>x.Key+"="+x.Value)));reported=true;}
            if(gap){Note("session_gap");return;}
            if(m<580 || m>925){Note("entry_time_filter");return;}
            if(pending || Position.MarketPosition!=MarketPosition.Flat){Note("position_or_pending");return;}
            if(entries>=4){Note("entry_limit");return;}
            double realized=SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit-startProfit-10*(SystemPerformance.AllTrades.Count-startTrades);
            if(realized<=-900){Note("daily_loss_limit");return;}
            long now=(utc.Ticks-621355968000000000L)*100;Feature f;
            if(!features.TryGetValue(now-60000000000L,out f)){Note("missing_feature");return;}
            if(!f.Eligible){Note("quote_quality_filter");return;}
            int side=CodexOfiOct5Gate.Signal(now,f.End,f.Last,f.Eligible,f.Score,f.Spread,OfiThreshold);
            if(side==0){Note(f.Spread>4?"spread_filter":"ofi_threshold_filter");return;}
            string signal=side==1?"L":"S";
            Print(string.Format(CultureInfo.InvariantCulture,"SIGNAL {0:yyyy-MM-ddTHH:mm:ss} side={1} featureEnd={2} lastSource={3} score={4:R} spread={5:R}",end,signal,f.End,f.Last,f.Score,f.Spread));
            SetStopLoss(signal,CalculationMode.Ticks,48,false);pending=true;entries++;Note("entry_submitted");
            if(side==1)EnterLong(1,signal);else EnterShort(1,signal);
        }
        protected override void OnOrderUpdate(Order order,double limitPrice,double stopPrice,int quantity,int filled,double averageFillPrice,OrderState orderState,DateTime time,ErrorCode error,string comment)
        {
            if((order.Name=="L"||order.Name=="S")&&(orderState==OrderState.Filled||orderState==OrderState.Cancelled||orderState==OrderState.Rejected))pending=false;
            if(error!=ErrorCode.NoError)Print("ORDER_ERROR "+error+" "+comment);
        }
        protected override void OnExecutionUpdate(Execution execution,string executionId,double price,int quantity,MarketPosition marketPosition,string orderId,DateTime time)
        {Print("CLOCK_EXEC|"+execution.Time.ToString("o",CultureInfo.InvariantCulture)+"|"+execution.Time.Ticks+"|"+time.ToString("o",CultureInfo.InvariantCulture)+"|"+time.Ticks+"|"+Time[0].ToString("o",CultureInfo.InvariantCulture)+"|"+execution.Order.Name+"|"+price.ToString("R",CultureInfo.InvariantCulture)+"|"+quantity+"|"+State);
            if(execution.Order!=null && (execution.Order.Name=="L"||execution.Order.Name=="S") && marketPosition!=MarketPosition.Flat)entryBar=CurrentBar;}
    }
}
