# -*- coding: utf-8 -*-
"""
excel_export.py
ส่งออกผลการสแกนเป็นไฟล์ Excel ตามฟอร์แมต passengers.xlsx
คอลัมน์: thai_name | english_name | passport   (ชื่อชีต: Sheet)

มีออปชั่นเพิ่ม "review mode" = เพิ่มคอลัมน์ source/note/file ไว้ตรวจทาน
"""

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

HEADERS = ["thai_name", "english_name", "passport"]
REVIEW_HEADERS = ["thai_name", "english_name", "passport", "source", "note", "file"]


def export_excel(rows, out_path, review=False, font_name="TH Sarabun New"):
    """
    rows: list ของ dict ที่มีคีย์ thai_name, english_name, passport (+ source/note/file)
    out_path: path ไฟล์ .xlsx ที่จะบันทึก
    review: True = ใส่คอลัมน์ตรวจทาน (source/note/file) และไฮไลต์แถวที่อ่านไม่ครบ
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"

    headers = REVIEW_HEADERS if review else HEADERS

    header_font = Font(name=font_name, bold=True, size=14)
    cell_font = Font(name=font_name, size=13)
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    warn_fill = PatternFill("solid", fgColor="FFF3CD")  # เหลืองอ่อน = ต้องตรวจ
    header_fill = PatternFill("solid", fgColor="D9E1F2")

    # หัวตาราง
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # ข้อมูล
    for r, row in enumerate(rows, start=2):
        incomplete = not (row.get("thai_name") and row.get("english_name")
                          and row.get("passport"))
        for c, h in enumerate(headers, 1):
            val = row.get(h, "")
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = cell_font
            cell.border = border
            cell.alignment = Alignment(vertical="center")
            if incomplete and h in ("thai_name", "english_name", "passport"):
                cell.fill = warn_fill

    # ความกว้างคอลัมน์
    widths = {"thai_name": 34, "english_name": 34, "passport": 16,
              "source": 12, "note": 30, "file": 24}
    for c, h in enumerate(headers, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = widths.get(h, 18)

    ws.freeze_panes = "A2"
    wb.save(out_path)
    return out_path
