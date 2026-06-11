#!/bin/bash
# ============================================
# Attendance Report System - One Click Runner
# نظام تقارير الحضور - تشغيل بضغطة واحدة
# ============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
@echo off
chcp 65001 > nul

echo "======================================"
echo "  نظام تقارير الحضور والانصراف"
echo "  Attendance Report System"
echo "======================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 غير مثبت. يرجى تثبيته أولاً."
    exit 1
fi

# Check openpyxl
python3 -c "import openpyxl, pandas" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 تثبيت المكتبات المطلوبة..."
    pip3 install openpyxl pandas --quiet
fi

# Check input file
if [ -z "$(ls "$SCRIPT_DIR/input/"*.xlsx 2>/dev/null)" ]; then
    echo "❌ لا يوجد ملف Excel في مجلد input/"
    echo "   ضع ملف البيانات في: input/attendance.xlsx"
    exit 1
fi

echo "🚀 جاري تشغيل البرنامج..."
echo ""
python3 "$SCRIPT_DIR/process_attendance.py"

echo ""
echo "📁 التقارير محفوظة في مجلد: output/"
echo "======================================"
