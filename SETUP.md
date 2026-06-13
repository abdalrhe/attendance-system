# دليل الإعداد والتشغيل
# SETUP — Attendance Report System

---

## 🗂️ هيكل المشروع

```
attendance-system/
│
├── run.bat                    ← ← ← تشغيل بضغطة واحدة (هذا الملف)
├── process_attendance.py      ← برنامج Python للتقارير
│
├── fetcher/
│   ├── ZKFetcher.csproj       ← مشروع C#
│   ├── src/
│   │   └── Program.cs         ← كود سحب البيانات
│   ├── lib/
│   │   └── zkemkeeper.dll     ← ← ← يجب نسخها هنا (انظر الخطوة 2)
│   └── bin/
│       └── ZKFetcher.exe      ← ← ← الملف المُجمَّع (بعد Build)
│
├── input/                     ← ملفات البيانات (xlsx أو csv)
└── output/                    ← تقارير الموظفين
```

---

## ⚙️ خطوات الإعداد (مرة واحدة فقط)

---

### الخطوة 1 — تثبيت المتطلبات

**Python:**
- حمّل من: https://python.org (3.10 أو أحدث)
- أثناء التثبيت: ✅ فعّل "Add Python to PATH"

**Visual Studio أو .NET SDK:**
- حمّل .NET Framework 4.8 Developer Pack:
  https://dotnet.microsoft.com/download/dotnet-framework/net48

---

### الخطوة 2 — الحصول على zkemkeeper.dll

هذا الملف يأتي مع برنامج ZKTeco الرسمي.

**الطريقة الأولى (من البرنامج المثبت):**
```
C:\Program Files (x86)\ZKTime\zkemkeeper.dll
   أو
C:\Program Files\ZKTime5.0\zkemkeeper.dll
```

**الطريقة الثانية (من الـ SDK):**
- اطلب ZKTeco SDK من الموزع
- أو حمّل من: https://github.com/adrobinoga/zk-protocol

بعد إيجاد الملف:
```
انسخ zkemkeeper.dll  →  attendance-system\fetcher\lib\
```

---

### الخطوة 3 — تسجيل zkemkeeper.dll في Windows

افتح CMD كـ Administrator وشغّل:
```cmd
regsvr32 "C:\path\to\attendance-system\fetcher\lib\zkemkeeper.dll"
```
يجب أن تظهر رسالة نجاح.

---

### الخطوة 4 — تعديل IP الجهاز

افتح الملف:
```
fetcher\src\Program.cs
```

عدّل هذا السطر:
```csharp
const string DEVICE_IP = "192.168.1.201";   // ← عدّل هذا
const int    DEVICE_PORT = 4370;             // ← غالباً لا تحتاج تغييره
```

**كيف تعرف IP الجهاز؟**
- من شاشة الجهاز: Menu → Comm → Ethernet → IP Address
- أو من برنامج ZKTime في قسم Device

---

### الخطوة 5 — بناء برنامج C#

**الطريقة الأولى (Visual Studio):**
1. افتح `fetcher\ZKFetcher.csproj`
2. Build → Build Solution
3. انسخ الـ exe الناتج إلى `fetcher\bin\`

**الطريقة الثانية (Command Line):**
```cmd
cd attendance-system\fetcher
dotnet build -c Release -o bin
```

---

### الخطوة 6 — تشغيل النظام

بعد اكتمال الإعداد:

```
انقر نقراً مزدوجاً على:  run.bat
```

أو من CMD:
```cmd
cd attendance-system
run.bat
```

---

## 🔧 إعدادات قوانين الدوام

لتعديل أوقات الدوام، افتح `process_attendance.py` وعدّل:

```python
SHIFT_MORNING = {
    "start": time(7, 0),     # بداية الدوام الصباحي
    "grace": time(7, 30),    # فترة السماح
    "end":   time(15, 0),    # نهاية الدوام
}

SHIFT_EVENING = {
    "start": time(15, 0),    # بداية الدوام المسائي
    "grace": time(15, 15),   # فترة السماح
    "end":   time(23, 0),    # نهاية الدوام
}

MISSING_PUNCH = 120          # دقائق عند غياب البصمة
```

---

## ❓ مشاكل شائعة

| المشكلة | الحل |
|---------|------|
| فشل الاتصال بالجهاز | تحقق من IP + الجهاز في نفس الشبكة |
| خطأ zkemkeeper | تأكد من تسجيل الـ DLL بـ regsvr32 |
| ZKFetcher.exe غير موجود | شغّل Build أولاً (الخطوة 5) |
| لا توجد بيانات في CSV | تحقق من إعدادات التاريخ في جهاز ZKTeco |
| Python not found | أعد تثبيت Python مع "Add to PATH" |

---

## 📞 تواصل

المطور: Ali Abdalrhim  
Telegram: @ALIcisco  
GitHub: github.com/abdalrhe
