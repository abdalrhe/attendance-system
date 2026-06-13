using System;
using System.IO;
using System.Text;
using System.Runtime.InteropServices;
using System.Collections.Generic;

namespace ZKFetcher
{
    static class ZK
    {
        const string DLL = "zkemkeeper.dll";

        [DllImport(DLL, EntryPoint = "Z_Connect_NET", CharSet = CharSet.Ansi, CallingConvention = CallingConvention.StdCall)]
        public static extern bool Connect_NET(string ip, int port);

        [DllImport(DLL, EntryPoint = "Disconnect", CallingConvention = CallingConvention.StdCall)]
        public static extern void Disconnect();

        [DllImport(DLL, EntryPoint = "GetLastError", CallingConvention = CallingConvention.StdCall)]
        public static extern void GetLastError(ref int err);

        [DllImport(DLL, EntryPoint = "ReadAllUserID", CallingConvention = CallingConvention.StdCall)]
        public static extern bool ReadAllUserID(int machineNo);

        [DllImport(DLL, EntryPoint = "ReadGeneralLogData", CallingConvention = CallingConvention.StdCall)]
        public static extern bool ReadGeneralLogData(int machineNo);

        [DllImport(DLL, EntryPoint = "SSR_GetAllUserInfoW", CharSet = CharSet.Unicode, CallingConvention = CallingConvention.StdCall)]
        public static extern bool SSR_GetAllUserInfoW(
            int machineNo,
            StringBuilder enrollNo,
            StringBuilder name,
            StringBuilder password,
            ref int privilege,
            ref bool enabled);

        [DllImport(DLL, EntryPoint = "SSR_GetGeneralLogDataWW", CharSet = CharSet.Unicode, CallingConvention = CallingConvention.StdCall)]
        public static extern bool SSR_GetGeneralLogDataWW(
            int machineNo,
            StringBuilder enrollNo,
            ref int verifyMode,
            ref int inOutMode,
            ref int year, ref int month, ref int day,
            ref int hour, ref int minute, ref int second,
            ref int workCode);
    }

    class Program
    {
        const string DEVICE_IP   = "192.168.1.201"; // ← عدّل هذا
        const int    DEVICE_PORT = 4370;
        const int    MACHINE_NO  = 1;

        static readonly string OUTPUT_CSV = Path.GetFullPath(
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "input", "attendance_raw.csv")
        );

        static void Main(string[] args)
        {
            Console.OutputEncoding = Encoding.UTF8;
            string ip   = args.Length > 0 ? args[0] : DEVICE_IP;
            int    port = args.Length > 1 ? int.Parse(args[1]) : DEVICE_PORT;

            Console.WriteLine("==============================================");
            Console.WriteLine("  ZKTeco MB10-VL - Data Fetcher");
            Console.WriteLine("==============================================");

            string dllPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "zkemkeeper.dll");
            if (!File.Exists(dllPath))
            {
                Console.WriteLine("[ERROR] zkemkeeper.dll not found next to ZKFetcher.exe");
                Console.WriteLine($"        Expected: {dllPath}");
                Environment.Exit(1);
            }
            Console.WriteLine("[OK] DLL found");

            Console.WriteLine($"[...] Connecting to {ip}:{port}");
            bool connected = ZK.Connect_NET(ip, port);
            if (!connected)
            {
                int err = 0;
                ZK.GetLastError(ref err);
                Console.WriteLine($"[ERROR] Connection failed (code: {err})");
                Console.WriteLine("        Check IP and network connection");
                Environment.Exit(1);
            }
            Console.WriteLine("[OK] Connected");

            // اسماء الموظفين
            var nameMap = new Dictionary<string, string>();
            try
            {
                ZK.ReadAllUserID(MACHINE_NO);
                var eno  = new StringBuilder(24);
                var name = new StringBuilder(24);
                var pass = new StringBuilder(24);
                int priv = 0;
                bool ena = false;
                while (ZK.SSR_GetAllUserInfoW(MACHINE_NO, eno, name, pass, ref priv, ref ena))
                {
                    string key = eno.ToString().Trim();
                    string val = name.ToString().Trim();
                    nameMap[key] = string.IsNullOrWhiteSpace(val) ? $"EMP_{key}" : val;
                    eno.Clear(); name.Clear(); pass.Clear(); priv = 0; ena = false;
                }
                Console.WriteLine($"[OK] {nameMap.Count} employees found");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WARN] Could not read names: {ex.Message}");
            }

            // سجلات الحضور
            Console.WriteLine("[...] Reading attendance logs...");
            if (!ZK.ReadGeneralLogData(MACHINE_NO))
            {
                Console.WriteLine("[ERROR] Failed to read attendance data");
                ZK.Disconnect();
                Environment.Exit(1);
            }

            var records = new List<(string name, DateTime date, TimeSpan time)>();
            var enroll  = new StringBuilder(24);
            int verify = 0, inOut = 0, y = 0, mo = 0, d = 0, h = 0, mi = 0, s = 0, wc = 0;

            while (ZK.SSR_GetGeneralLogDataWW(MACHINE_NO, enroll,
                   ref verify, ref inOut,
                   ref y, ref mo, ref d,
                   ref h, ref mi, ref s, ref wc))
            {
                string emp = nameMap.ContainsKey(enroll.ToString().Trim())
                    ? nameMap[enroll.ToString().Trim()]
                    : $"EMP_{enroll}";
                records.Add((emp, new DateTime(y, mo, d), new TimeSpan(h, mi, s)));
                enroll.Clear();
                verify = inOut = y = mo = d = h = mi = s = wc = 0;
            }

            ZK.Disconnect();
            Console.WriteLine($"[OK] {records.Count} punches fetched");
            Console.WriteLine("[OK] Disconnected");

            var daily = Process(records);
            Save(daily);
            Console.WriteLine($"[OK] Saved {daily.Count} daily records");
            Console.WriteLine($"     File: {OUTPUT_CSV}");
            Console.WriteLine("[DONE]");
        }

        static List<(string, DateTime, TimeSpan?, TimeSpan?)> Process(
            List<(string name, DateTime date, TimeSpan time)> raw)
        {
            var g = new Dictionary<string, List<TimeSpan>>();
            foreach (var r in raw)
            {
                string k = $"{r.name}|||{r.date:yyyy-MM-dd}";
                if (!g.ContainsKey(k)) g[k] = new List<TimeSpan>();
                g[k].Add(r.time);
            }
            var result = new List<(string, DateTime, TimeSpan?, TimeSpan?)>();
            foreach (var kv in g)
            {
                var p = kv.Key.Split(new[]{"|||"}, StringSplitOptions.None);
                var times = kv.Value; times.Sort();
                TimeSpan? inT = null, outT = null;
                if (times.Count == 1) { if (times[0].Hours < 12) inT = times[0]; else outT = times[0]; }
                else { inT = times[0]; outT = times[times.Count - 1]; }
                result.Add((p[0], DateTime.Parse(p[1]), inT, outT));
            }
            result.Sort((a, b) => {
                int c = string.Compare(a.Item1, b.Item1);
                return c != 0 ? c : a.Item2.CompareTo(b.Item2);
            });
            return result;
        }

        static void Save(List<(string name, DateTime date, TimeSpan? inT, TimeSpan? outT)> records)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(OUTPUT_CSV));
            using var w = new StreamWriter(OUTPUT_CSV, false, new UTF8Encoding(true));
            w.WriteLine("Name,Date,Check In,Check Out");
            foreach (var r in records)
            {
                string i = r.inT.HasValue  ? $"{r.inT.Value.Hours:D2}:{r.inT.Value.Minutes:D2}:00"  : "";
                string o = r.outT.HasValue ? $"{r.outT.Value.Hours:D2}:{r.outT.Value.Minutes:D2}:00" : "";
                w.WriteLine($"{r.name},{r.date:M/d/yyyy},{i},{o}");
            }
        }
    }
}
