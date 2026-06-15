#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
أداة تشخيص الاتصال بجهاز ZKTeco
تجرب كل التركيبات الممكنة وتعرض تفاصيل كاملة
"""

import sys
from zk import ZK
from zk import const

DEVICE_IP   = "192.168.1.201"
DEVICE_PORT = 4370

attempts = [
    {"password": 123456,  "force_udp": False, "label": "TCP, password=0"},
    {"password": 123456,  "force_udp": True,  "label": "UDP, password=0"},
]

print("=" * 50)
print("  ZKTeco Connection Diagnostics")
print(f"  Target: {DEVICE_IP}:{DEVICE_PORT}")
print("=" * 50)

for att in attempts:
    print(f"\n[TEST] {att['label']}")
    print("-" * 40)

    zk = ZK(
        DEVICE_IP,
        port=DEVICE_PORT,
        timeout=8,
        password=att["password"],
        force_udp=att["force_udp"],
        ommit_ping=True,
        verbose=True,
    )

    try:
        conn = zk.connect()
        print(f"\n>>> ✅ SUCCESS with: {att['label']}")
        print(f">>> Firmware: {conn.get_firmware_version()}")
        print(f">>> Serial:   {conn.get_serialnumber()}")
        try:
            users = conn.get_users()
            print(f">>> Users found: {len(users)}")
            for u in users[:5]:
                print(f"      uid={u.user_id} name='{u.name}'")
        except Exception as e:
            print(f">>> get_users error: {e}")
        conn.disconnect()
        print(f"\n*** USE THIS CONFIG: password={att['password']}, force_udp={att['force_udp']} ***")
        sys.exit(0)
    except Exception as e:
        print(f">>> ❌ FAILED: {type(e).__name__}: {e}")

print("\n" + "=" * 50)
print("All attempts failed.")
print("=" * 50)
