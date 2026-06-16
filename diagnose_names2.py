#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تشخيص متقدم: قراءة بيانات المستخدمين الخام بالكامل
للبحث عن الاسم العربي المخزّن في حقل بيانات موسّع
"""

from zk import ZK
from zk import const

DEVICE_IP   = "192.168.1.201"
DEVICE_PORT = 4370
DEVICE_PASS = 123456

zk = ZK(DEVICE_IP, port=DEVICE_PORT, timeout=15, password=DEVICE_PASS,
        force_udp=False, ommit_ping=True)

conn = zk.connect()
print("[OK] Connected\n")

# نطلب بيانات المستخدمين الخام مباشرة من الجهاز (بدون تفسير pyzk)
command = const.CMD_USERTEMP_RRQ
fct = const.FCT_USER
userdata, size = conn.read_with_buffer(command, fct=fct)

print(f"Raw data size: {size}")
print(f"First 300 bytes (hex):")
print(userdata[:300].hex())
print()
print(f"First 300 bytes (latin1 repr):")
print(repr(userdata[:300].decode('latin1', errors='replace')))
print()

# نحاول قراءة أول سجل مستخدم بالحجم الافتراضي (72 byte) وأحجام أخرى محتملة
for rec_size in [72, 92, 88, 28, 16]:
    print(f"\n=== Trying record size: {rec_size} ===")
    if len(userdata) >= rec_size * 3:
        for i in range(3):
            chunk = userdata[i*rec_size:(i+1)*rec_size]
            print(f"Record {i}: hex={chunk[:40].hex()}")
            try:
                txt = chunk.decode('latin1', errors='replace')
                print(f"  latin1: {txt!r}")
            except Exception:
                pass

conn.disconnect()
