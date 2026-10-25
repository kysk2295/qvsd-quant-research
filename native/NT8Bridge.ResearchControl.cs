// Local research control. Does not submit orders or enable strategies.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Media;
using NinjaTrader.Cbi;

namespace NinjaTrader.NinjaScript.AddOns
{
    public partial class NT8Bridge
    {
        private static bool Research_Flag(out double age)
        {
            age = -1;
            string path = Path.Combine(Core.Globals.UserDataDir, "bin", "Custom", "AddOns", "research.enabled");
            if (!File.Exists(path)) return false;
            age = (DateTime.UtcNow - File.GetLastWriteTimeUtc(path)).TotalHours;
            return age >= -0.002 && age <= 24;
        }

        private static List<ConnectOptions> Research_Profiles()
        {
            var result = new List<ConnectOptions>();
            var configured = Core.Globals.ConnectOptions;
            if (configured != null) for (int i = 0; i < configured.Count; i++) result.Add(configured[i]);
            var brokerage = Core.Globals.BrokerageConnectOptions;
            if (brokerage != null) result.AddRange(brokerage.ToArray());
            return result.Where(o => o != null).GroupBy(o => o.Name + "\n" + o.Provider).Select(g => g.First()).ToList();
        }

        private static bool Research_Allowed(ConnectOptions o)
        {
            // Provider7 is NT8's built-in Kinetick free EOD profile on this version.
            return o.Provider == Provider.Playback || o.Provider == Provider.Simulator
                || (o.Provider.ToString() == "Provider7" && o.Name == "Kinetick – End Of Day (Free)")
                || (o.IsDataProviderOnly && !o.CanManageOrders);
        }

        private static string Research_ProfilesJson()
        {
            return Arr(Research_Profiles().Select(o => Obj(P("name", Q(o.Name)),
                P("provider", Q(o.Provider.ToString())), P("allowed", Research_Allowed(o) ? "true" : "false"),
                P("isDataProviderOnly", o.IsDataProviderOnly ? "true" : "false"),
                P("canManageOrders", o.CanManageOrders ? "true" : "false"))));
        }

        private static string Route_ResearchControl(string method, string[] seg,
            System.Collections.Specialized.NameValueCollection q, string body, ref int status)
        {
            if (seg.Length != 2 || seg[0] != "research") return null;
            if (method == "GET" && seg[1] == "status")
            {
                double age; bool armed = Research_Flag(out age);
                return Obj(P("version", Q("1.0")), P("armed", armed ? "true" : "false"),
                    P("profiles", Research_ProfilesJson()),
                    P("capabilities", Q("connection connect/disconnect; research window tree/actions; independent playback control; chart/indicator controls; historical download; backtest")));
            }
            if (method == "GET" && (seg[1] == "window" || seg[1] == "screenshot"))
            {
                try { return seg[1] == "window" ? Research_Window(q["title"]) : Research_Screenshot(q["title"]); }
                catch (BadRequestException ex) { return Err(ref status, 400, ex.Message); }
            }
            if (method == "GET" && seg[1] == "chart") return Research_WindowSnapshot(FindChart(q["chart"] ?? "first"), "Chart");
            if (method != "POST" || !(seg[1] == "connect" || seg[1] == "disconnect" || seg[1] == "action" || seg[1] == "open")) return null;
            double flagAge;
            if (!Research_Flag(out flagAge)) return Err(ref status, 403, "research.enabled absent or older than 24 hours");
            try
            {
                var req = ParseJson(body) as Dictionary<string, object>;
                if (req == null) return Err(ref status, 400, "JSON object required");
                string result;
                if (seg[1] == "action") result = Research_Action(req);
                else if (seg[1] == "open") result = Research_Open(JGetStr(req, "title", "Historical Data"));
                else
                {
                    string name = JGetStr(req, "name", "");
                    var matches = Research_Profiles().Where(o => o.Name == name).ToList();
                    if (matches.Count != 1) return Err(ref status, 400, "connection name must match exactly one saved profile");
                    var opt = matches[0];
                    if (!Research_Allowed(opt)) return Err(ref status, 403, "order-routing broker profiles are outside research control");
                    string exposure = Data_Exposure();
                    if (exposure != null) return Err(ref status, 409, exposure);
                    Window center; lock (gate) center = windows.FirstOrDefault(w => w is Gui.ControlCenter);
                    if (center == null) return Err(ref status, 409, "Control Center unavailable");
                    var existing = ConnSnapshot().FirstOrDefault(c => c.Options != null && c.Options.Name == name);
                    if (seg[1] == "connect")
                    {
                        if (existing == null || !IsConnected(existing))
                            Ui(center.Dispatcher, () => { Connection.Connect(opt); return true; });
                    }
                    else if (existing != null)
                        Ui(center.Dispatcher, () => { existing.Disconnect(); return true; });
                    result = Obj(P("requested", "true"), P("name", Q(name)), P("operation", Q(seg[1])),
                        P("note", Q("asynchronous; verify with nt_connections before continuing")));
                }
                Log("research " + seg[1] + " completed");
                return result;
            }
            catch (BadRequestException ex) { return Err(ref status, 400, ex.Message); }
        }

        private static Window Research_FindWindow(string title)
        {
            long requestedHandle = 0;
            int split = title.LastIndexOf('|');
            if (split >= 0)
            {
                if (!long.TryParse(title.Substring(split + 1), out requestedHandle) || requestedHandle <= 0)
                    throw new BadRequestException("invalid explicit research window handle");
                title = title.Substring(0, split);
            }
            if (!(title == "Historical Data" || title == "Strategy Analyzer" || title == "Playback" || title == "Warning" || title == "Error" || title == "Control Center"))
                throw new BadRequestException("only research and Control Center windows are readable");
            HashSet<Window> owned; var all = KnownWindows(out owned);
            var found = all.Where(w => Ui(w.Dispatcher, () => TitleOf(w) == title &&
                (requestedHandle == 0 || new System.Windows.Interop.WindowInteropHelper(w).Handle.ToInt64() == requestedHandle))).ToArray();
            if (found.Length != 1) throw new BadRequestException("expected exactly one open " + title + " window");
            return found[0];
        }

        private static List<FrameworkElement> Research_Controls(Window win)
        {
            var result = new List<FrameworkElement>();
            var todo = new Queue<DependencyObject>(); todo.Enqueue(win);
            var seen = new HashSet<DependencyObject>();
            while (todo.Count > 0 && seen.Count < 5000)
            {
                var current = todo.Dequeue(); if (!seen.Add(current)) continue;
                var fe = current as FrameworkElement;
                if (fe is PasswordBox) continue;
                if (fe != null && fe.IsVisible && (fe is Control || fe is TextBlock)) result.Add(fe);
                if (current is Visual || current is System.Windows.Media.Media3D.Visual3D)
                {
                    int count = VisualTreeHelper.GetChildrenCount(current);
                    for (int i = 0; i < count; i++) todo.Enqueue(VisualTreeHelper.GetChild(current, i));
                }
                foreach (var child in LogicalTreeHelper.GetChildren(current))
                    if (child is DependencyObject) todo.Enqueue((DependencyObject)child);
            }
            return result;
        }

        private static string Research_Label(FrameworkElement fe)
        {
            var text = fe as TextBlock; if (text != null) return text.Text;
            var box = fe as TextBox; if (box != null) return box.Text;
            var content = fe as ContentControl;
            if (content != null && (content.Content is string || content.Content is DateTime)) return content.Content.ToString();
            var header = fe as HeaderedContentControl;
            if (header != null && header.Header is string) return (string)header.Header;
            var menu = fe as HeaderedItemsControl;
            if (menu != null && menu.Header is string) return (string)menu.Header;
            return System.Windows.Automation.AutomationProperties.GetName(fe);
        }

        private static string Research_Fields(FrameworkElement fe)
        {
            var fields = new List<string>();
            foreach (string name in new[] { "Value", "SelectedDate", "SelectedText", "Instrument", "Text", "IsChecked", "IsExpanded", "SelectedIndex" })
            {
                var pi = fe.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.Instance);
                if (pi == null || !pi.CanRead || pi.GetIndexParameters().Length != 0) continue;
                try
                {
                    object v = pi.GetValue(fe, null);
                    if (v == null || v is string || v is bool || v is DateTime || v is int || v is double || v is Instrument)
                        fields.Add(P(name, Q(v == null ? null : (v is DateTime ? ((DateTime)v).ToString("o") : v.ToString()))));
                }
                catch { }
            }
            return Obj(fields.ToArray());
        }

        private sealed class Research_Snapshot
        {
            public Window Window;
            public DateTime Created;
            public List<FrameworkElement> Controls;
        }
        private static readonly Dictionary<string, Research_Snapshot> Research_Snapshots = new Dictionary<string, Research_Snapshot>();

        private static string Research_Window(string title)
        {
            var win = Research_FindWindow(title);
            return Research_WindowSnapshot(win, title);
        }

        private static string Research_WindowSnapshot(Window win, string title)
        {
            return Ui(win.Dispatcher, () =>
            {
                var controls = Research_Controls(win); string token = Guid.NewGuid().ToString("N");
                lock (Research_Snapshots)
                {
                    Research_Snapshots.Clear();
                    Research_Snapshots[token] = new Research_Snapshot { Window = win, Created = DateTime.UtcNow, Controls = controls };
                }
                return Obj(P("snapshot", Q(token)), P("title", Q(title)), P("controls", Arr(controls.Select((fe, i) =>
                    Obj(P("id", I(i)), P("type", Q(fe.GetType().Name)), P("name", Q(fe.Name)),
                        P("label", Q(Research_Label(fe))), P("fields", Research_Fields(fe)), P("enabled", fe.IsEnabled ? "true" : "false"),
                        P("items", fe is ComboBox ? Arr(((ComboBox)fe).Items.Cast<object>().Select(v => Q(v.ToString()))) : "[]"))))));
            });
        }

        private static string Research_Action(Dictionary<string, object> req)
        {
            string token = JGetStr(req, "snapshot", ""); int id = JGetInt(req, "id", -1);
            string action = JGetStr(req, "action", ""); string value = JGetStr(req, "value", "");
            Research_Snapshot snap;
            lock (Research_Snapshots)
            {
                if (!Research_Snapshots.TryGetValue(token, out snap)) throw new BadRequestException("stale snapshot; read window again");
                Research_Snapshots.Remove(token); // one action per observation
            }
            if ((DateTime.UtcNow - snap.Created).TotalSeconds > 120 || id < 0 || id >= snap.Controls.Count)
                throw new BadRequestException("expired snapshot or invalid control id");
            string exposure = Data_Exposure(); if (exposure != null) throw new BadRequestException(exposure);
            return Ui(snap.Window.Dispatcher, () =>
            {
                string windowTitle = TitleOf(snap.Window);
                var fe = snap.Controls[id]; if (!fe.IsVisible || !fe.IsEnabled) throw new BadRequestException("control unavailable");
                if (windowTitle == "Warning" || windowTitle == "Error")
                {
                    string label = Research_Label(fe);
                    string message = string.Join("\n", snap.Controls.OfType<TextBlock>().Select(t => t.Text));
                    bool ownAddonTrust = label == "_Yes" && message.Contains("detected new add on(s): NT8Bridge.ResearchControl.")
                        && JGetBool(req, "authorizeResearchAddon", false);
                    if (action != "invoke" || !(fe is Button) || !(label == "OK" || label == "Ok" || label == "확인" || ownAddonTrust))
                        throw new BadRequestException("diagnostic dialogs allow only their observed OK button");
                    ((Button)fe).RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
                    return Obj(P("ok", "true"), P("note", Q("diagnostic acknowledged; read state again")));
                }
                bool chartInstrument = snap.Window is Gui.Chart.Chart && action == "set"
                    && fe.GetType().Name == "InstrumentSelector" && JGetStr(req, "property", "Value") == "Instrument";
                if (chartInstrument)
                {
                    var chart = (Gui.Chart.Chart)snap.Window;
                    bool enabled = OnChart(chart, cc => cc.Strategies != null && cc.Strategies.Any(s => s != null && s.IsEnabled));
                    if (enabled) throw new BadRequestException("chart has an enabled strategy");
                }
                bool analyzer = windowTitle == "Strategy Analyzer";
                if (analyzer)
                {
                    var selector = snap.Controls.OfType<Gui.Tools.NinjaScriptSelector>().SingleOrDefault();
                    if (selector == null || selector.SelectedText != "CodexCloseMomentum")
                        throw new BadRequestException("Analyzer pilot requires observed CodexCloseMomentum");
                    if (action == "invoke" && (!(fe is Button) || Research_Label(fe) != "Run"))
                        throw new BadRequestException("Analyzer pilot permits only Run button");
                }
                if (!(windowTitle == "Historical Data" || windowTitle == "Playback" || analyzer || chartInstrument))
                    throw new BadRequestException("actions only supported on research windows");
                if (action == "invoke" && fe is Button)
                {
                    // Historical data only: no delete/import/export/order buttons.
                    string label = Research_Label(fe);
                    if (!(analyzer && label == "Run") && label != "Download" && label != "다운로드" && label != "Get Market Replay data")
                        throw new BadRequestException("button is outside download allowlist: " + label);
                    var button = (Button)fe;
                    if (analyzer && button.Command != null)
                    {
                        var routed = button.Command as System.Windows.Input.RoutedCommand;
                        if (routed != null)
                        {
                            var target = button.CommandTarget ?? button;
                            if (!routed.CanExecute(button.CommandParameter, target)) throw new BadRequestException("Run command unavailable");
                            routed.Execute(button.CommandParameter, target);
                        }
                        else
                        {
                            if (!button.Command.CanExecute(button.CommandParameter)) throw new BadRequestException("Run command unavailable");
                            button.Command.Execute(button.CommandParameter);
                        }
                    }
                    else button.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
                }
                else if (action == "select" && fe is TabItem) ((TabItem)fe).IsSelected = true;
                else if (action == "expand" && fe is Expander) ((Expander)fe).IsExpanded = true;
                else if (action == "check" && fe is ToggleButton) ((ToggleButton)fe).IsChecked = bool.Parse(value);
                else if (action == "select" && fe is ComboBox)
                {
                    var box = (ComboBox)fe; var matches = box.Items.Cast<object>().Where(v => v.ToString() == value).ToArray();
                    if (matches.Length != 1) throw new BadRequestException("option must match one observed item");
                    box.SelectedItem = matches[0];
                }
                else if (action == "set" && fe is TextBox)
                {
                    ((TextBox)fe).Text = value;
                    var binding = ((TextBox)fe).GetBindingExpression(TextBox.TextProperty);
                    if (binding != null) binding.UpdateSource();
                }
                else if (action == "set" && fe is DatePicker) ((DatePicker)fe).SelectedDate = DateTime.ParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture);
                else if (action == "set")
                {
                    string property = JGetStr(req, "property", "Value");
                    if (analyzer && fe.GetType().FullName == "NinjaTrader.Gui.TradePerformance.DisplayModeSelector" && property == "Display")
                    {
                        if (value != "Trades" && value != "Summary") throw new BadRequestException("Only Trades or Summary view permitted");
                        var display = fe.GetType().GetProperty("Display");
                        display.SetValue(fe, Enum.Parse(display.PropertyType, value), null);
                        return Obj(P("ok", "true"), P("note", Q("read view again")));
                    }
                    if (property != "Value" && property != "Instrument") throw new BadRequestException("custom control property must be Value or Instrument");
                    var pi = fe.GetType().GetProperty(property, BindingFlags.Public | BindingFlags.Instance);
                    if (pi == null || !pi.CanWrite) throw new BadRequestException("property unavailable");
                    Type t = Nullable.GetUnderlyingType(pi.PropertyType) ?? pi.PropertyType;
                    if (t == typeof(object))
                    {
                        object current = pi.GetValue(fe, null);
                        if (current is DateTime) t = typeof(DateTime);
                    }
                    object converted;
                    if (t == typeof(DateTime)) converted = DateTime.ParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture);
                    else if (t == typeof(Instrument)) converted = Instrument.GetInstrument(value);
                    else if (t == typeof(int)) converted = int.Parse(value, CultureInfo.InvariantCulture);
                    else if (t == typeof(double)) converted = double.Parse(value, CultureInfo.InvariantCulture);
                    else throw new BadRequestException("unsupported property type");
                    pi.SetValue(fe, converted, null);
                }
                else throw new BadRequestException("unsupported action/control pair");
                return Obj(P("ok", "true"), P("note", Q("read a new window snapshot to verify the result")));
            });
        }

        private static string Research_Open(string title)
        {
            if (title != "Historical Data" && title != "Strategy Analyzer") throw new BadRequestException("only Historical Data or Strategy Analyzer may be opened");
            Window center; lock (gate) center = windows.FirstOrDefault(w => w is Gui.ControlCenter);
            if (center == null) throw new BadRequestException("Control Center unavailable");
            return Ui(center.Dispatcher, () =>
            {
                var types = typeof(Gui.ControlCenter).Assembly.GetTypes().Where(t => typeof(Window).IsAssignableFrom(t)
                    && (title == "Historical Data" ? (t.Name == "HistoricalData" || t.Name == "HistoricalDataWindow")
                        : t.FullName == "NinjaTrader.Gui.NinjaScript.StrategyAnalyzer.StrategyAnalyzer")).ToArray();
                if (types.Length != 1) throw new BadRequestException("research window type unresolved");
                var win = (Window)Activator.CreateInstance(types[0]); win.Show();
                return Obj(P("requested", "true"), P("title", Q(title)));
            });
        }

        private static string Research_Screenshot(string title)
        {
            var win = Research_FindWindow(title);
            return Ui(win.Dispatcher, () =>
            {
                int width = (int)Math.Ceiling(win.ActualWidth), height = (int)Math.Ceiling(win.ActualHeight);
                if (width <= 0 || height <= 0 || width > 8192 || height > 8192) throw new BadRequestException("window has invalid size");
                var image = new System.Windows.Media.Imaging.RenderTargetBitmap(width, height, 96, 96, PixelFormats.Pbgra32);
                image.Render(win);
                var encoder = new System.Windows.Media.Imaging.PngBitmapEncoder();
                encoder.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(image));
                string dir = Path.Combine(Core.Globals.UserDataDir, "NT8Bridge", "screenshots"); Directory.CreateDirectory(dir);
                string path = Path.Combine(dir, "research-" + Guid.NewGuid().ToString("N") + ".png");
                using (var stream = File.Create(path)) encoder.Save(stream);
                return Obj(P("path", Q(path)), P("width", I(width)), P("height", I(height)));
            });
        }
    }
}
