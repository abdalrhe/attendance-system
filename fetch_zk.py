#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZKTeco MB10-VL Fetcher (pyzk)
سحب بيانات الحضور من جهاز البصمة وحفظها CSV
يقرأ أسماء الموظفين العربية مباشرة من البيانات الخام (ترميز cp1256)
"""

import sys
import csv
import os
import struct
from collections import defaultdict

try:
    from zk import ZK, const
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

# ترميز الأسماء العربية على هذا الجهاز (تأكدنا منه بالتشخيص الخام)
NAME_ENCODING = "cp1256"

# تركيب سجل المستخدم (72 بايت) — نفس تنسيق pyzk الرسمي
# <H  uid (2 بايت)
#  B  privilege (1 بايت)
# 8s  password (8 بايت)
# 24s name (24 بايت)   <-- هنا الاسم العربي
#  I  card (4 بايت)
#  x  padding (1 بايت)
# 7s  group_id (7 بايت)
#  x  padding (1 بايت)
# 24s user_id (24 بايت)
USER_STRUCT_FMT = '<HB8s24sIx7sx24s'
USER_RECORD_SIZE = 72


def read_arabic_names(conn):
    """
    يقرأ بيانات المستخدمين الخام من الجهاز ويستخرج الاسم العربي
    بترميز cp1256 بدل الاعتماد على تفسير pyzk الافتراضي (الذي يُرجع NN-x
    لأنه يحاول فك الاسم بترميز utf-8/latin1 فيفشل).
    يُرجع: dict {uid_str: name}
    """
    name_map = {}
    try:
        command = const.CMD_USERTEMP_RRQ
        fct = const.FCT_USER
        userdata, size = conn.read_with_buffer(command, fct=fct)
    except Exception as e:
        print(f"[WARN] Could not read raw user buffer: {e}")
        return name_map

    if not userdata or len(userdata) <= 4:
        return name_map

    # أول 4 بايتات = total_size header (مثل ما يفعل pyzk) — يجب تجاوزها
    userdata = userdata[4:]

    while len(userdata) >= USER_RECORD_SIZE:
        chunk = userdata[:USER_RECORD_SIZE]
        try:
            uid, privilege, password, name, card, group_id, user_id = struct.unpack(
                USER_STRUCT_FMT, chunk
            )
        except struct.error:
            break

        name_clean = name.split(b"\x00")[0]
        try:
            name_decoded = name_clean.decode(NAME_ENCODING, errors="strict").strip()
        except UnicodeDecodeError:
            # احتياط: اسم لاتيني أو بيانات تالفة
            name_decoded = name_clean.decode("ascii", errors="ignore").strip()

        if uid > 0 and name_decoded:
            name_map[str(uid)] = name_decoded

        userdata = userdata[USER_RECORD_SIZE:]

    return name_map


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

    # --- أسماء الموظفين (العربية، من البيانات الخام) ---
    print("[...] Reading users (raw, arabic-aware)...")
    name_map = read_arabic_names(conn)

    if name_map:
        print(f"[OK] {len(name_map)} arabic names extracted")
        for uid, nm in list(name_map.items())[:5]:
            print(f"      uid={uid} -> {nm}")
    else:
        print("[WARN] Raw read failed, falling back to pyzk get_users()")
        try:
            users = conn.get_users()
            for u in users:
                uid = str(u.user_id)
                nm = (u.name or "").strip()
                name_map[uid] = nm if nm else f"EMP_{uid}"
        except Exception as e:
            print(f"[WARN] Fallback also failed: {e}")

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
