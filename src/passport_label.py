"""
สร้างไฟล์ PDF "ใบติดพาสปอร์ต" (Alfayard 1441)

รูปแบบ 1 ใบ (กว้าง 8.4 ซม. สูงแล้วแต่ดีไซน์):
  ซ้าย  : โลโก้บริษัท + ALFAYARD 1441 CO., LTD. + อีเมล + เบอร์โทร
  ขวา   : ตาราง
            Name        <ชื่อจาก Excel>        No.      <ลำดับอัตโนมัติ>
            Grp.Leader  <ชื่อผู้นำกลุ่ม (พิมพ์เองได้)>
            Grp.Name    <AL-FAYARD>            Grp.No.  <แก้ได้ก่อนสร้าง>

- ไม่มีรูปคน (รูปติดแยกกับพาสปอร์ต)
- ค่าต่าง ๆ อยู่บรรทัดเดียวกับหัวข้อ ย่อฟอนต์อัตโนมัติ ถ้ายังยาวเกินจะตัดเป็น 2 บรรทัด
- No. เรียงตามลำดับรายชื่อใน Excel (1, 2, 3, ...)
- วาง 2 คอลัมน์/หน้า A4 เรียงจากบนลงล่าง

แก้ค่า layout ได้ที่ src/config.py (ส่วน "ใบติดพาสปอร์ต")
"""
import os
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
from PIL import Image

from . import config
from .generator import register_fonts, fit_font_size, _draw_text_line, FONT_REG, FONT_BD


# ---------- สี ----------
_BLACK = (0, 0, 0)
_GREY = (0.30, 0.30, 0.30)
_EMAIL_BLUE = (0.13, 0.29, 0.62)
_LINE = (0.55, 0.55, 0.55)


def _sw(text, font, size):
    return pdfmetrics.stringWidth(text, font, size)


def _load_logo(base_dir):
    """คืน ImageReader ของโลโก้ (ถ้ามี) พร้อมอัตราส่วน กว้าง/สูง"""
    path = os.path.join(base_dir, config.PLABEL_LOGO)
    if not os.path.exists(path):
        return None, 1.0
    img = Image.open(path)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    ratio = img.width / img.height if img.height else 1.0
    return ImageReader(buf), ratio


def _wrap_value(text, font, max_w, start_pt, min_pt):
    """
    คืน list ของ (บรรทัด, ขนาดฟอนต์)
    - พยายามให้อยู่บรรทัดเดียวก่อน (ย่อถึง start_pt..min_pt)
    - ถ้าบรรทัดเดียวเล็กเกิน min_pt ยังไม่พอ → ตัดเป็น 2 บรรทัดตามคำ
    """
    text = (text or "").strip()
    if not text:
        return []
    # ลองบรรทัดเดียว
    size = fit_font_size(text, font, max_w, start_pt, min_pt)
    if _sw(text, font, size) <= max_w:
        return [(text, size)]
    # ตัด 2 บรรทัดตามคำ (แบ่งให้สองฝั่งกว้างใกล้กัน)
    words = text.split()
    if len(words) >= 2:
        best = None
        for k in range(1, len(words)):
            l1 = " ".join(words[:k]); l2 = " ".join(words[k:])
            w = max(_sw(l1, font, start_pt), _sw(l2, font, start_pt))
            if best is None or w < best[0]:
                best = (w, l1, l2)
        _, l1, l2 = best
        s1 = fit_font_size(l1, font, max_w, start_pt, min_pt)
        s2 = fit_font_size(l2, font, max_w, start_pt, min_pt)
        s = min(s1, s2)
        return [(l1, s), (l2, s)]
    # คำเดียวยาวมาก — ย่อสุด
    return [(text, min_pt)]


def _draw_field(c, label_x, right_bound, row_top, row_h,
                label, value, value_font=FONT_BD,
                value_start=None, value_min=None, value_color=_BLACK):
    """
    วาด 'หัวข้อ + ค่า' ในแถวหนึ่ง จัดกึ่งกลางแนวตั้งของแถว (รองรับค่า 2 บรรทัด)
    ค่าเริ่มถัดจากหัวข้อแบบไดนามิก เพื่อให้ชื่ออยู่บรรทัดเดียวได้กว้างที่สุด
    right_bound = ขอบขวาสุดที่ค่าวางได้
    """
    vs_start = value_start if value_start else config.PLABEL_VALUE_PT
    vs_min = value_min if value_min else config.PLABEL_VALUE_MIN_PT
    center_y = row_top - row_h / 2.0

    # หัวข้อ: baseline ที่กึ่งกลางแถว
    lbl_size = config.PLABEL_LABEL_PT
    _draw_text_line(c, label_x, center_y - lbl_size * 0.34,
                    label, FONT_BD, lbl_size, _GREY)

    value_x = label_x + _sw(label, FONT_BD, lbl_size) + config.PLABEL_KEY_GAP_MM * mm
    value_max_w = right_bound - value_x
    lines = _wrap_value(value, value_font, value_max_w, vs_start, vs_min)

    if not lines:
        return
    if len(lines) == 1:
        txt, sz = lines[0]
        _draw_text_line(c, value_x, center_y - sz * 0.34, txt, value_font, sz, value_color)
    else:
        sz = lines[0][1]
        line_h = sz * 1.12
        first_base = center_y + line_h / 2.0 - sz * 0.34
        for i, (txt, _s) in enumerate(lines):
            _draw_text_line(c, value_x, first_base - i * line_h,
                            txt, value_font, sz, value_color)


def _draw_no_cell(c, cx, row_top, cw, row_h, label, value):
    """คอลัมน์แคบด้านขวา: หัวข้อเล็กบน + เลขใหญ่กลาง"""
    tpad = 1.3 * mm
    _draw_text_line(c, cx + tpad, row_top - config.PLABEL_LABEL_PT - 0.5 * mm,
                    label, FONT_REG, config.PLABEL_LABEL_PT, _GREY)
    vs = config.PLABEL_VALUE_PT
    if _sw(value, FONT_BD, vs) > cw - 2 * tpad:
        vs = fit_font_size(value, FONT_BD, cw - 2 * tpad, vs, 6)
    w = _sw(value, FONT_BD, vs)
    _draw_text_line(c, cx + cw / 2.0 - w / 2.0,
                    row_top - row_h + (row_h - vs) / 2.0 + 0.3 * mm,
                    value, FONT_BD, vs, _BLACK)


def _draw_left(c, x, y, base_dir, logo_reader, logo_ratio):
    """ฝั่งซ้าย: จัดกลุ่ม โลโก้ + ข้อความบริษัท เป็นก้อนเดียว กึ่งกลางแนวตั้ง"""
    H = config.PLABEL_H_MM * mm
    pad = config.PLABEL_PAD_MM * mm
    left_w = config.PLABEL_LEFT_W_MM * mm
    lcx = x + left_w / 2.0
    avail_w = left_w - 2 * pad

    comp_lines = [
        (config.PLABEL_COMPANY_NAME, FONT_BD, config.PLABEL_COMPANY_PT, _BLACK),
        (config.PLABEL_EMAIL, FONT_REG, config.PLABEL_CONTACT_PT, _EMAIL_BLUE),
        (config.PLABEL_PHONE, FONT_REG, config.PLABEL_CONTACT_PT, _GREY),
    ]
    lead = config.PLABEL_COMPANY_LEADING
    comp_h = sum(sz * lead for _, _, sz, _ in comp_lines)

    # ขนาดโลโก้: สูงตามที่ตั้ง แต่ไม่เกินความกว้างที่มี
    logo_h = config.PLABEL_LOGO_H_MM * mm
    logo_w = logo_h * logo_ratio
    if logo_w > avail_w:
        logo_w = avail_w
        logo_h = logo_w / logo_ratio if logo_ratio else logo_w
    has_logo = logo_reader is not None
    gap = config.PLABEL_LOGO_GAP_MM * mm if has_logo else 0.0

    group_h = (logo_h if has_logo else 0.0) + gap + comp_h
    group_top = y + H / 2.0 + group_h / 2.0     # กึ่งกลางแนวตั้ง

    cy = group_top
    if has_logo:
        c.drawImage(logo_reader, lcx - logo_w / 2.0, cy - logo_h,
                    width=logo_w, height=logo_h,
                    preserveAspectRatio=True, mask="auto")
        cy -= logo_h + gap

    for text, font, size, color in comp_lines:
        s = size
        if _sw(text, font, s) > avail_w:
            s = fit_font_size(text, font, avail_w, s, 5)
        cy -= s * lead
        w = _sw(text, font, s)
        _draw_text_line(c, lcx - w / 2.0, cy, text, font, s, color)


def _draw_label(c, x, y, person, no, base_dir, logo_reader, logo_ratio,
                grp_leader, grp_name, grp_no):
    """วาดใบติดพาสปอร์ต 1 ใบ; (x, y) = มุมล่างซ้าย"""
    W = config.PLABEL_W_MM * mm
    H = config.PLABEL_H_MM * mm
    left_w = config.PLABEL_LEFT_W_MM * mm
    no_w = config.PLABEL_NO_W_MM * mm
    tpad = config.PLABEL_TEXT_PAD_MM * mm

    # ---- กรอบนอก + เส้นแบ่งซ้าย/ขวา ----
    c.setLineWidth(0.7)
    c.setStrokeColorRGB(*_LINE)
    c.rect(x, y, W, H, stroke=1, fill=0)
    div_x = x + left_w
    c.setLineWidth(0.5)
    c.line(div_x, y, div_x, y + H)

    # ---- ฝั่งซ้าย ----
    _draw_left(c, x, y, base_dir, logo_reader, logo_ratio)

    # ---- ฝั่งขวา: ตาราง 3 แถว ----
    row_h = H / 3.0
    y_r1_top = y + H
    y_r2_top = y + 2 * row_h
    y_r3_top = y + row_h
    c.setLineWidth(0.4)
    c.setStrokeColorRGB(*_LINE)
    c.line(div_x, y_r2_top, x + W, y_r2_top)
    c.line(div_x, y_r3_top, x + W, y_r3_top)

    no_x = x + W - no_w
    c.line(no_x, y_r1_top, no_x, y_r2_top)
    c.line(no_x, y_r3_top, no_x, y)

    label_x = div_x + tpad
    rb_narrow = no_x - tpad          # ขอบขวาของค่าในแถวที่มีคอลัมน์ No.
    rb_full = (x + W) - tpad         # ขอบขวาของค่าในแถวเต็ม (Grp.Leader)

    eng = str(person.get(config.COL_ENGLISH, "")).strip()
    thai = str(person.get(config.COL_THAI, "")).strip()
    name_value = eng if eng else thai

    _draw_field(c, label_x, rb_narrow, y_r1_top, row_h, "Name", name_value)
    _draw_no_cell(c, no_x, y_r1_top, no_w, row_h, "No.", str(no))

    _draw_field(c, label_x, rb_full, y_r2_top, row_h, "Grp.Leader", grp_leader)

    _draw_field(c, label_x, rb_narrow, y_r3_top, row_h, "Grp.Name", grp_name)
    _draw_no_cell(c, no_x, y_r3_top, no_w, row_h, "Grp.No.", str(grp_no))


def generate_passport_labels(people, base_dir, output_path,
                             grp_leader="", grp_name="AL-FAYARD", grp_no="1",
                             start_no=1):
    """
    people   : list ของ dict [{thai_name, english_name, passport}, ...]
    grp_leader / grp_name / grp_no : ค่าที่แก้ได้ก่อนสร้าง (เหมือนกันทุกใบ)
    start_no : เลข No. เริ่มต้น (ปกติ 1)
    คืนค่า จำนวนใบที่สร้าง
    """
    register_fonts(base_dir)
    logo_reader, logo_ratio = _load_logo(base_dir)

    c = canvas.Canvas(output_path, pagesize=A4)
    page_w, page_h = A4

    cols = config.PLABEL_COLS
    rows = config.PLABEL_ROWS
    per_page = cols * rows

    W = config.PLABEL_W_MM * mm
    H = config.PLABEL_H_MM * mm
    gx = config.PLABEL_GUTTER_X_MM * mm
    gy = config.PLABEL_GUTTER_Y_MM * mm

    grid_w = cols * W + (cols - 1) * gx
    grid_h = rows * H + (rows - 1) * gy
    margin_x = (page_w - grid_w) / 2.0
    margin_y = (page_h - grid_h) / 2.0

    for i, person in enumerate(people):
        slot = i % per_page
        if i > 0 and slot == 0:
            c.showPage()
        col = slot % cols
        row = slot // cols
        x = margin_x + col * (W + gx)
        y = page_h - margin_y - (row + 1) * H - row * gy
        _draw_label(c, x, y, person, start_no + i, base_dir,
                    logo_reader, logo_ratio, grp_leader, grp_name, grp_no)

    c.showPage()
    c.save()
    return len(people)
