#!/usr/bin/env python3
"""
Attendance Report Automation System
نظام استخراج تقارير الحضور والانصراف
"""

import pandas as pd
import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter
from openpyxl.styles.numbers import FORMAT_NUMBER
import os
import sys
from datetime import datetime, time, timedelta
import re

# ========================
# CONFIGURATION / الإعدادات
# ========================

SHIFT_MORNING = {
    "name": "صباحي",
    "start": time(7, 0),
    "grace": time(7, 30),
    "end": time(15, 0),
}

SHIFT_EVENING = {
    "name": "مسائي",
    "start": time(15, 0),
    "grace": time(15, 15),
    "end": time(23, 0),
    "early_grace": time(22, 30),
}

MISSING_PUNCH = 120  # دقائق عند غياب البصمة

# Colors
COLOR_HEADER_BG    = "1F4E79"   # dark blue
COLOR_HEADER_FONT  = "FFFFFF"
COLOR_TITLE_BG     = "2E75B6"
COLOR_ALT_ROW      = "DEEAF1"
COLOR_TOTAL_BG     = "F2F2F2"
COLOR_LATE_BG      = "FFE0E0"
COLOR_EARLY_BG     = "FFF3CD"
COLOR_OK_BG        = "E8F5E9"
COLOR_RED          = "C00000"
COLOR_ORANGE       = "ED7D31"
COLOR_GREEN        = "375623"


# ========================
# HELPER FUNCTIONS
# ========================

def parse_time(val):
    """Convert various time formats to datetime.time"""
    if pd.isna(val):
        return None
    if isinstance(val, time):
        return val
    if isinstance(val, datetime):
        return val.time()
    if isinstance(val, str):
        val = val.strip()
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(val, fmt).time()
            except ValueError:
                pass
    return None


def minutes_between(t1: time, t2: time) -> int:
    """Minutes from t1 to t2 (can be negative)"""
    d = datetime(2000, 1, 1)
    return int((datetime.combine(d, t2) - datetime.combine(d, t1)).total_seconds() // 60)


def calc_late(in_time, late_shift: dict) -> int:
    """Calculate late minutes based on shift rules"""
    if in_time is None:
        return MISSING_PUNCH
    grace = late_shift["grace"]
    start = late_shift["start"]
    if in_time <= grace:
        return 0
    return minutes_between(start, in_time)


def calc_early_leave(out_time, early_shift: dict) -> int:
    """Calculate early leave minutes"""
    if out_time is None:
        return MISSING_PUNCH
    end = early_shift["end"]
    if out_time >= end:
        return 0
    return minutes_between(out_time, end)


def detect_shift(in_time, out_time) -> dict:
    """Detect which shift based on clock-in time"""
    if in_time is None:
        if out_time and out_time >= time(15, 0):
            return SHIFT_EVENING
        return SHIFT_MORNING
    if in_time >= time(14, 0):
        return SHIFT_EVENING
    return SHIFT_MORNING


def fmt_minutes(m: int) -> str:
    if m == 0:
        return "0"
    h = m // 60
    mn = m % 60
    if h > 0:
        return f"{h}س {mn}د" if mn else f"{h}س"
    return f"{mn}د"


def time_str(t: time | None) -> str:
    if t is None:
        return "—"
    return t.strftime("%H:%M")


def fmt_date(d) -> str:
    if pd.isna(d):
        return ""
    if isinstance(d, str):
        return d
    try:
        return pd.to_datetime(d).strftime("%Y/%m/%d")
    except Exception:
        return str(d)


# ========================
# EXCEL STYLE HELPERS
# ========================

def thin_border():
    s = Side(style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)


def medium_border():
    s = Side(style="medium", color="1F4E79")
    return Border(left=s, right=s, top=s, bottom=s)


def header_cell(ws, row, col, value, merge_end_col=None):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(name="Arial", bold=True, color=COLOR_HEADER_FONT, size=11)
    cell.fill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = thin_border()
    if merge_end_col:
        ws.merge_cells(start_row=row, start_column=col,
                       end_row=row, end_column=merge_end_col)
    return cell


def title_cell(ws, row, col, value, merge_end_col=None):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(name="Arial", bold=True, color=COLOR_HEADER_FONT, size=14)
    cell.fill = PatternFill("solid", fgColor=COLOR_TITLE_BG)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    if merge_end_col:
        ws.merge_cells(start_row=row, start_column=col,
                       end_row=row, end_column=merge_end_col)
    return cell


def data_cell(ws, row, col, value, bg=None, bold=False, color=None, align="center"):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(name="Arial", size=10, bold=bold,
                     color=color if color else "000000")
    if bg:
        cell.fill = PatternFill("solid", fgColor=bg)
    cell.alignment = Alignment(horizontal=align, vertical="center")
    cell.border = thin_border()
    return cell


# ========================
# PROCESS DATA
# ========================

def load_data(filepath: str) -> pd.DataFrame:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(filepath, encoding="utf-8-sig")
    else:
        df = pd.read_excel(filepath)
    col_map = {}
    for c in df.columns:
        cl = str(c).lower().strip()
        if "name" in cl or "اسم" in cl:
            col_map[c] = "name"
        elif "date" in cl or "تاريخ" in cl:
            col_map[c] = "date"
        elif ("check in" in cl) or ("in" in cl and "out" not in cl) or "دخول" in cl or "حضور" in cl:
            col_map[c] = "in_time"
        elif ("check out" in cl) or ("out" in cl) or "خروج" in cl or "انصراف" in cl:
            col_map[c] = "out_time"
    df.rename(columns=col_map, inplace=True)
    required = {"name", "date", "in_time", "out_time"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"أعمدة مفقودة: {missing}\nالأعمدة الموجودة: {list(df.columns)}")
    return df


def process_employee(records: list) -> list:
    rows = []
    for r in records:
        date = r.get("date")
        if pd.isna(date) if not isinstance(date, str) else not date.strip():
            continue
        in_t = parse_time(r.get("in_time"))
        out_t = parse_time(r.get("out_time"))
        shift = detect_shift(in_t, out_t)
        late = calc_late(in_t, shift)
        early = calc_early_leave(out_t, shift)
        rows.append({
            "date": date,
            "in_time": in_t,
            "out_time": out_t,
            "shift": shift["name"],
            "late": late,
            "early": early,
        })
    return rows


# ========================
# GENERATE REPORT
# ========================

def generate_report(employee_name: str, rows: list, output_dir: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "تقرير الحضور"
    ws.sheet_view.rightToLeft = True
    ws.sheet_properties.tabColor = "2E75B6"

    # Row heights
    ws.row_dimensions[1].height = 15
    ws.row_dimensions[2].height = 40
    ws.row_dimensions[3].height = 20
    ws.row_dimensions[4].height = 28
    ws.row_dimensions[5].height = 28

    # Column widths
    col_widths = {1: 6, 2: 16, 3: 12, 4: 12, 5: 12, 6: 16, 7: 16}
    for col, w in col_widths.items():
        ws.column_dimensions[get_column_letter(col)].width = w

    # ---- Title ----
    title_cell(ws, 2, 1, f"تقرير الحضور والانصراف — {employee_name}", merge_end_col=7)
    ws.row_dimensions[2].height = 40

    # ---- Info row ----
    ws.merge_cells("A3:G3")
    info = ws["A3"]
    info.value = f"تاريخ الإصدار: {datetime.now().strftime('%Y/%m/%d')}"
    info.font = Font(name="Arial", size=9, italic=True, color="666666")
    info.alignment = Alignment(horizontal="center")

    # ---- Column Headers ----
    headers = ["#", "التاريخ", "وقت الدخول", "وقت الخروج", "الوردية", "التأخير", "الخروج المبكر"]
    for col, h in enumerate(headers, 1):
        header_cell(ws, 4, col, h)

    # ---- Data Rows ----
    total_late = 0
    total_early = 0

    for i, row in enumerate(rows, 1):
        r = i + 4
        ws.row_dimensions[r].height = 22
        bg = COLOR_ALT_ROW if i % 2 == 0 else None

        late = row["late"]
        early = row["early"]
        total_late += late
        total_early += early

        # Row bg based on issues
        if late > 0 and early > 0:
            row_bg = "FFD5D5"
        elif late > 0:
            row_bg = COLOR_LATE_BG
        elif early > 0:
            row_bg = COLOR_EARLY_BG
        else:
            row_bg = bg

        data_cell(ws, r, 1, i, bg=row_bg)
        data_cell(ws, r, 2, fmt_date(row["date"]), bg=row_bg)
        data_cell(ws, r, 3, time_str(row["in_time"]), bg=row_bg,
                  color=COLOR_RED if row["in_time"] is None else None)
        data_cell(ws, r, 4, time_str(row["out_time"]), bg=row_bg,
                  color=COLOR_RED if row["out_time"] is None else None)
        data_cell(ws, r, 5, row["shift"], bg=row_bg)
        data_cell(ws, r, 6, fmt_minutes(late), bg=row_bg,
                  bold=late > 0, color=COLOR_RED if late > 0 else COLOR_GREEN)
        data_cell(ws, r, 7, fmt_minutes(early), bg=row_bg,
                  bold=early > 0, color=COLOR_ORANGE if early > 0 else COLOR_GREEN)

    # ---- Totals ----
    total_row = len(rows) + 5
    ws.row_dimensions[total_row].height = 28
    ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=5)
    tc = ws.cell(row=total_row, column=1, value="الإجمالي")
    tc.font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
    tc.fill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
    tc.alignment = Alignment(horizontal="center", vertical="center")
    tc.border = thin_border()

    late_cell = ws.cell(row=total_row, column=6, value=fmt_minutes(total_late))
    late_cell.font = Font(name="Arial", bold=True, size=11,
                          color=COLOR_RED if total_late > 0 else COLOR_GREEN)
    late_cell.fill = PatternFill("solid", fgColor=COLOR_TOTAL_BG)
    late_cell.alignment = Alignment(horizontal="center", vertical="center")
    late_cell.border = thin_border()

    early_cell = ws.cell(row=total_row, column=7, value=fmt_minutes(total_early))
    early_cell.font = Font(name="Arial", bold=True, size=11,
                           color=COLOR_ORANGE if total_early > 0 else COLOR_GREEN)
    early_cell.fill = PatternFill("solid", fgColor=COLOR_TOTAL_BG)
    early_cell.alignment = Alignment(horizontal="center", vertical="center")
    early_cell.border = thin_border()

    # ---- Summary box (below table) ----
    s = total_row + 2
    ws.row_dimensions[s].height = 22
    ws.row_dimensions[s + 1].height = 22
    ws.row_dimensions[s + 2].height = 22

    def summary_row(r, label, value, val_color):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        lc = ws.cell(row=r, column=1, value=label)
        lc.font = Font(name="Arial", bold=True, size=10)
        lc.alignment = Alignment(horizontal="right", vertical="center")
        lc.fill = PatternFill("solid", fgColor="F2F2F2")
        lc.border = thin_border()
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=7)
        vc = ws.cell(row=r, column=4, value=value)
        vc.font = Font(name="Arial", bold=True, size=11, color=val_color)
        vc.alignment = Alignment(horizontal="center", vertical="center")
        vc.fill = PatternFill("solid", fgColor="FFFFFF")
        vc.border = thin_border()

    summary_row(s,     "عدد أيام الحضور:", len(rows), "1F4E79")
    summary_row(s + 1, "مجموع دقائق التأخير:", fmt_minutes(total_late),
                COLOR_RED if total_late > 0 else COLOR_GREEN)
    summary_row(s + 2, "مجموع دقائق الخروج المبكر:", fmt_minutes(total_early),
                COLOR_ORANGE if total_early > 0 else COLOR_GREEN)

    # ---- Legend ----
    leg = s + 4
    ws.merge_cells(start_row=leg, start_column=1, end_row=leg, end_column=7)
    lc = ws.cell(row=leg, column=1, value="🔴 تأخير    🟡 خروج مبكر    ✅ حضور وانصراف منتظم    — لا توجد بصمة")
    lc.font = Font(name="Arial", size=9, italic=True, color="666666")
    lc.alignment = Alignment(horizontal="center")

    # ---- Print setup ----
    ws.print_title_rows = "4:4"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1

    # Save
    safe_name = re.sub(r'[\\/*?:"<>|]', '_', employee_name.strip())
    out_path = os.path.join(output_dir, f"{safe_name}.xlsx")
    wb.save(out_path)
    return out_path


# ========================
# MAIN
# ========================

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(base, "input")
    output_dir = os.path.join(base, "output")
    os.makedirs(output_dir, exist_ok=True)

    # Find input file — CSV (من الجهاز) له أولوية على xlsx
    csv_files  = [f for f in os.listdir(input_dir) if f.endswith(".csv")]
    xlsx_files = [f for f in os.listdir(input_dir) if f.endswith(".xlsx")]
    all_files  = csv_files + xlsx_files
    if not all_files:
        print("❌ لم يتم العثور على ملف بيانات في مجلد input")
        print("   ضع ملف xlsx أو attendance_raw.csv")
        sys.exit(1)

    input_file = os.path.join(input_dir, all_files[0])
    print(f"📂 قراءة الملف: {all_files[0]}")

    df = load_data(input_file)

    # Filter out summary/total rows
    df = df[df["name"].notna()]
    df = df[~df["name"].astype(str).str.strip().isin(["المجموع", "Total", "الإجمالي", ""])]

    # Group by employee
    employees = df.groupby("name")
    print(f"👥 عدد الموظفين: {len(employees)}")

    generated = []
    for name, group in employees:
        name = str(name).strip()
        records = group.to_dict("records")
        rows = process_employee(records)
        if not rows:
            print(f"  ⚠️  {name}: لا توجد بيانات صالحة")
            continue
        path = generate_report(name, rows, output_dir)
        total_late = sum(r["late"] for r in rows)
        total_early = sum(r["early"] for r in rows)
        print(f"  ✅ {name} → {len(rows)} يوم | تأخير: {fmt_minutes(total_late)} | خروج مبكر: {fmt_minutes(total_early)}")
        generated.append(path)

    print(f"\n✅ تم إنشاء {len(generated)} تقرير في مجلد output/")
    return generated


if __name__ == "__main__":
    main()
