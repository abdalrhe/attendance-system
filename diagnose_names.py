#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تشخيص ترميز أسماء الموظفين العربية من جهاز ZKTeco
"""

from zk import ZK
from zk.user import User

DEVICE_IP   = "192.168.1.201"
DEVICE_PORT = 4370
DEVICE_PASS = 123456

zk = ZK(DEVICE_IP, port=DEVICE_PORT, timeout=15, password=DEVICE_PASS,
        force_udp=False, ommit_ping=True)

conn = zk.connect()
print("[OK] Connected\n")

# نوصل مباشرة لدالة الجهاز الخام بدون تفسير pyzk
conn._ZK__nextcommand = True  # تجاوز بعض الكاش الداخلي إن وجد (احتياطي)

users = conn.get_users()
print(f"Total users: {len(users)}\n")
print("=" * 70)

for u in users[:15]:
    raw_name = u.name
    print(f"uid={u.user_id}")
    print(f"  repr(name)     = {raw_name!r}")
    print(f"  type           = {type(raw_name)}")

    if isinstance(raw_name, str):
        try:
            raw_bytes = raw_name.encode('utf-8', errors='replace')
            print(f"  utf8 bytes     = {raw_bytes}")
        except Exception as e:
            print(f"  encode error: {e}")

        # نجرب فك إعادة الترميز بعدة طرق شائعة لأجهزة ZK الصينية
        for enc_from, enc_to in [
            ("latin1", "gb2312"),
            ("latin1", "gbk"),
            ("latin1", "cp1256"),
            ("latin1", "utf-8"),
            ("cp1252", "cp1256"),
        ]:
            try:
                fixed = raw_name.encode(enc_from, errors="ignore").decode(enc_to, errors="ignore")
                if fixed.strip() and fixed != raw_name:
                    print(f"  try {enc_from}->{enc_to}: {fixed!r}")
            except Exception:
                pass
    print("-" * 70)

conn.disconnect()
