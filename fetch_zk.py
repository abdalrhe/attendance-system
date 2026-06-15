#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZKTeco MB10-VL Fetcher (pyzk)
سحب بيانات الحضور من جهاز البصمة وحفظها CSV
"""

import sys
import csv
import os
from collections import defaultdict

try:
    from zk import ZK
except ImportError:
    print("[ERROR] pyzk not installed")
    print("        Run: pip install pyzk")
    sys.exit(1)

# ============================================================
#  إعدادات
# ============================================================
DEVICE_IP   = "192.168.1.201"
DEVICE_PORT = 4370
DEVICE_PASS = 123456
TIMEOUT     = 15

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV  = os.path.join(SCRIPT_DIR, "input", "attendance_raw.csv")


def main():
    print("=" * 46)
    print("  ZKTeco MB10-VL - Fetcher (pyzk)")
    print("=" * 46)

    zk = ZK(
        DEVICE_IP,
        port=DEVICE_PORT,
        timeout=TIMEOUT,
        password=DEVICE_PASS,
        force_udp=False,
        ommit_ping=True,
    )

    print(f"[...] Connecting to {DEVICE_IP}:{DEVICE_PORT}")
    try:
        conn = zk.connect()
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        sys.exit(1)

    print("[OK] Connected")
    try:
        print(f"     Firmware: {conn.get_firmware_version()}")
        print(f"     Serial:   {conn.get_serialnumber()}")
    except Exception:
        pass

    # --- أسماء الموظفين ---
    print("[...] Reading users...")
    name_map = {}
    try:
        users = conn.get_users()
        for u in users:
            uid = str(u.user_id)
            nm = (u.name or "").strip()
            name_map[uid] = nm if nm else f"EMP_{uid}"
        print(f"[OK] {len(name_map)} users found")
    except Exception as e:
        print(f"[WARN] Could not read users: {e}")

    # --- سجلات الحضور ---
    print("[...] Reading attendance logs (this may take a moment)...")
    try:
        attendances = conn.get_attendance()
        print(f"[OK] {len(attendances)} punches fetched")
    except Exception as e:
        print(f"[ERROR] Could not read attendance: {e}")
        conn.disconnect()
        sys.exit(1)

    conn.disconnect()
    print("[OK] Disconnected")

    if not attendances:
        print("[WARN] No attendance records found on device")
        sys.exit(0)

    # --- تجميع حسب الموظف + التاريخ ---
    print("[...] Processing...")
    grouped = defaultdict(list)
    for a in attendances:
        uid = str(a.user_id)
        d = a.timestamp.date()
        grouped[(uid, d)].append(a.timestamp)

    rows = []
    for (uid, d), times in grouped.items():
        times.sort()
        name = name_map.get(uid, f"EMP_{uid}")

        if len(times) == 1:
            t = times[0]
            if t.hour < 12:
                in_t, out_t = t, None
            else:
                in_t, out_t = None, t
        else:
            in_t, out_t = times[0], times[-1]

        rows.append({
            "name": name,
            "date": d,
            "in":  in_t.strftime("%H:%M:%S")  if in_t  else "",
            "out": out_t.strftime("%H:%M:%S") if out_t else "",
        })

    rows.sort(key=lambda r: (r["name"], r["date"]))

    # --- حفظ CSV ---
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Date", "Check In", "Check Out"])
        for r in rows:
            date_str = f"{r['date'].month}/{r['date'].day}/{r['date'].year}"
            writer.writerow([r["name"], date_str, r["in"], r["out"]])

    print(f"[OK] Saved {len(rows)} daily records")
    print(f"     File: {OUTPUT_CSV}")
    print(f"     Date range: {min(g[1] for g in grouped)} to {max(g[1] for g in grouped)}")
    print(f"     Unique employees: {len(set(r['name'] for r in rows))}")
    print("[DONE]")


if __name__ == "__main__":
    main()
