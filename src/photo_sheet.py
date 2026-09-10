"""
สร้างไฟล์ PDF "แผ่นรวมรูปคน" (Photo sheet) — สำหรับตัดไปแปะมุมล่างของพาสปอร์ต
คู่กับใบติดพาสปอร์ต: ใช้ No. เดียวกัน จับคู่ได้ง่าย

- ดึงรูปจากโฟลเดอร์รูป โดยจับคู่ด้วยเลขพาสปอร์ต (เหมือนใบติดกระเป๋า)
- center-crop ให้ได้ขนาด/อัตราส่วนตามที่ตั้ง (ค่าเริ่ม 22x28 มม.)
- มี No.+ชื่อ กำกับเหนือรูป (อยู่นอกเส้นตัด — ตัดเฉพาะรูปไปแปะ)
- คนไหนไม่มีรูป วาดกรอบ "NO PHOTO" ไว้ เพื่อคง No. ให้ตรงกับใบติด

แก้ค่า layout ได้ที่ src/config.py (ส่วน "แผ่นรวมรูปคน" — PSHEET_*)
"""
import os
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader

from . import config
from .generator import register_fonts, fit_font_size, _draw_text_line, FONT_REG, FONT_BD
from .photo import find_photo_path, prepare_photo


def _sw(text, font, size):
    return pdfmetrics.stringWidth(text, font, size)


def _draw_cell(c, x, y_top, no, name, photo_path):
    """
    วาด 1 ช่อง: No.+ชื่อ (บน) + รูป (ล่าง มีเส้นตัดรอบ)
    (x, y_top) = มุมบนซ้ายของช่อง
    """
    pw = config.PSHEET_PHOTO_W_MM * mm
    ph = config.PSHEET_PHOTO_H_MM * mm
    cap_h = config.PSHEET_CAP_H_MM * mm

    # ---- แคปชัน No.+ชื่อ (เหนือรูป) — เก็บ No. ให้ครบเสมอ ตัดชื่อท้ายด้วย … ถ้ายาวเกินรูป ----
    prefix = f"{no}. "
    cap = (prefix + (name or "")).strip().rstrip(".")
    cs = fit_font_size(cap, FONT_BD, pw, config.PSHEET_CAPTION_PT, 4.5)
    if _sw(cap, FONT_BD, cs) > pw and name:
        nm = name
        while nm and _sw(prefix + nm + "…", FONT_BD, cs) > pw:
            nm = nm[:-1]
        cap = prefix + nm.strip() + "…" if nm.strip() else prefix.strip()
    _draw_text_line(c, x, y_top - cap_h + 1.0 * mm, cap, FONT_BD, cs, (0, 0, 0))

    # ---- รูป (ใต้แคปชัน) ----
    py = y_top - cap_h - ph
    drawn = False
    if photo_path:
        try:
            img = prepare_photo(photo_path, config.PSHEET_PHOTO_W_MM, config.PSHEET_PHOTO_H_MM)
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            c.drawImage(ImageReader(buf), x, py, width=pw, height=ph)
            drawn = True
        except Exception:
            drawn = False
    if not drawn:
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.6, 0.6, 0.6)
        c.drawCentredString(x + pw / 2, py + ph / 2 - 3, "NO PHOTO")

    # ---- เส้นตัดรอบรูป ----
    if config.PSHEET_DRAW_BORDER:
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0.55, 0.55, 0.55)
        c.rect(x, py, pw, ph, stroke=1, fill=0)


def generate_photo_sheet(people, base_dir, output_path,
                         photos_dir=None, start_no=1):
    """
    people    : list ของ dict [{english_name/thai_name, passport}, ...] (ลำดับเดียวกับใบติด)
    photos_dir: โฟลเดอร์รูปคน (ชื่อไฟล์ = เลขพาสปอร์ต) — ไม่ระบุใช้ photos/ ในโปรเจกต์
    start_no  : เลข No. เริ่มต้น (ให้ตรงกับใบติด)
    คืนค่า (จำนวนรูปที่วาง, จำนวนคนที่ไม่มีรูป)
    """
    register_fonts(base_dir)
    c = canvas.Canvas(output_path, pagesize=A4)
    page_w, page_h = A4

    cols = config.PSHEET_COLS
    rows = config.PSHEET_ROWS
    per_page = cols * rows

    pw = config.PSHEET_PHOTO_W_MM * mm
    cell_w = pw
    cell_h = (config.PSHEET_CAP_H_MM + config.PSHEET_PHOTO_H_MM) * mm
    gx = config.PSHEET_GAP_X_MM * mm
    gy = config.PSHEET_GAP_Y_MM * mm

    grid_w = cols * cell_w + (cols - 1) * gx
    grid_h = rows * cell_h + (rows - 1) * gy
    margin_x = (page_w - grid_w) / 2.0
    margin_y = (page_h - grid_h) / 2.0

    missing = 0
    for i, person in enumerate(people):
        slot = i % per_page
        if i > 0 and slot == 0:
            c.showPage()
        col = slot % cols
        row = slot // cols
        x = margin_x + col * (cell_w + gx)
        y_top = page_h - margin_y - row * (cell_h + gy)

        passport = str(person.get(config.COL_PASSPORT, "")).strip()
        name = (str(person.get(config.COL_ENGLISH, "")).strip()
                or str(person.get(config.COL_THAI, "")).strip())
        path = find_photo_path(passport, base_dir, photos_dir) if passport else None
        if not path:
            missing += 1
        _draw_cell(c, x, y_top, start_no + i, name, path)

    c.showPage()
    c.save()
    return len(people), missing
