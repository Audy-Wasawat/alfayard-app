"""
สร้างไฟล์ PDF ใบติดกระเป๋า 8 ใบ/หน้า A4
- วาดตาราง 2x4
- แต่ละใบ: รูปคน + QR (ซ้าย), ชื่อไทย/อังกฤษ/พาสปอร์ต/บริษัท (ขวา)
- ชื่อไทย/อังกฤษ ย่อฟอนต์อัตโนมัติจาก 16pt ทีละ 1pt จนพอดี 1 บรรทัด
"""
import os
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

from . import config
from .photo import find_photo_path, prepare_photo

FONT_REG = "SarabunTH"
FONT_BD = "SarabunTH-Bold"


def register_fonts(base_dir):
    """ลงทะเบียนฟอนต์ไทยเพื่อฝังใน PDF"""
    reg = os.path.join(base_dir, config.FONT_REGULAR)
    bold = os.path.join(base_dir, config.FONT_BOLD)
    pdfmetrics.registerFont(TTFont(FONT_REG, reg))
    if os.path.exists(bold):
        pdfmetrics.registerFont(TTFont(FONT_BD, bold))
    else:
        # ถ้าไม่มีตัวหนา ใช้ตัวปกติแทน
        pdfmetrics.registerFont(TTFont(FONT_BD, reg))


def fit_font_size(text, font_name, max_width_pt, start_pt, min_pt):
    """
    หาขนาดฟอนต์ที่ใหญ่ที่สุด (ไม่เกิน start_pt) ที่ทำให้ text พอดี 1 บรรทัด
    ลดทีละ 1pt ตามที่ต้องการ ถ้าถึง min_pt แล้วยังเกิน ก็คืน min_pt
    """
    if not text:
        return start_pt
    size = start_pt
    while size > min_pt:
        w = pdfmetrics.stringWidth(text, font_name, size)
        if w <= max_width_pt:
            return size
        size -= 1
    return min_pt


def _draw_tag(c, x, y, person, base_dir, photos_dir=None, qr_path=None):
    """
    วาดใบติดกระเป๋า 1 ใบ โดย (x, y) = มุมล่างซ้ายของใบ (ระบบพิกัด reportlab)
    person = dict ที่มี thai_name, english_name, passport
    photos_dir/qr_path: ระบุแหล่งรูปคน/ไฟล์ QR เองได้ (ถ้าไม่ระบุใช้ค่า default)
    """
    tw = config.TAG_W_MM * mm
    th = config.TAG_H_MM * mm
    pad = config.PAD_MM * mm

    # เส้นขอบใบ (แนวตัด)
    if config.DRAW_CUT_BORDER:
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0.6, 0.6, 0.6)
        c.rect(x, y, tw, th, stroke=1, fill=0)

    # กรอบเนื้อหาภายใน
    inner_x = x + pad
    inner_top = y + th - pad          # ขอบบนภายใน
    inner_bottom = y + pad

    # ---------- คอลัมน์ซ้าย: รูปคน ----------
    photo_w = config.PHOTO_W_MM * mm
    photo_h = config.PHOTO_H_MM * mm
    photo_x = inner_x
    photo_y = inner_top - photo_h      # มุมล่างซ้ายของรูป

    passport = str(person.get(config.COL_PASSPORT, "")).strip()
    photo_path = find_photo_path(passport, base_dir, photos_dir) if passport else None
    if photo_path:
        try:
            pil_img = prepare_photo(photo_path, config.PHOTO_W_MM, config.PHOTO_H_MM)
            buf = BytesIO()
            pil_img.save(buf, format="PNG")
            buf.seek(0)
            c.drawImage(ImageReader(buf), photo_x, photo_y,
                        width=photo_w, height=photo_h)
        except Exception as e:
            _draw_placeholder(c, photo_x, photo_y, photo_w, photo_h, "IMG ERR")
    else:
        _draw_placeholder(c, photo_x, photo_y, photo_w, photo_h, "NO PHOTO")

    # ---------- คอลัมน์ซ้าย: QR (ใต้รูป) ----------
    qr_size = config.QR_SIZE_MM * mm
    qr_x = inner_x
    qr_y = photo_y - config.GAP_PHOTO_QR_MM * mm - qr_size
    qr_file = qr_path if qr_path else os.path.join(base_dir, config.QR_IMAGE)
    if qr_file and os.path.exists(qr_file):
        c.drawImage(qr_file, qr_x, qr_y, width=qr_size, height=qr_size,
                    preserveAspectRatio=True, mask="auto")
    else:
        _draw_placeholder(c, qr_x, qr_y, qr_size, qr_size, "QR")

    # ---------- คอลัมน์ขวา: ข้อความ ----------
    text_x = inner_x + photo_w + config.COL_GAP_MM * mm
    text_max_w = (x + tw - pad) - text_x    # ความกว้างสูงสุดของข้อความ

    thai = str(person.get(config.COL_THAI, "")).strip()
    eng = str(person.get(config.COL_ENGLISH, "")).strip()

    # ย่อฟอนต์ชื่อให้พอดี 1 บรรทัด
    thai_pt = fit_font_size(thai, FONT_BD, text_max_w,
                            config.NAME_START_PT, config.NAME_MIN_PT)
    eng_pt = fit_font_size(eng, FONT_REG, text_max_w,
                           config.NAME_START_PT, config.NAME_MIN_PT)

    # รายการบรรทัดข้อความ (บนลงล่าง)
    company_gap = config.COMPANY_GAP_MM * mm
    lines = [
        {"text": thai, "font": FONT_BD, "size": thai_pt, "color": (0, 0, 0)},
        {"text": eng, "font": FONT_REG, "size": eng_pt, "color": (0, 0, 0)},
        {"text": passport, "font": FONT_REG, "size": config.PASSPORT_PT,
         "color": (0, 0, 0)},
        {"text": config.COMPANY_NAME, "font": FONT_REG, "size": config.COMPANY_PT,
         "color": (0.15, 0.15, 0.15), "gap_before": company_gap},
    ]

    # ความสูงรวมของบล็อกข้อความ (ผลรวมของ advance แต่ละบรรทัด + ระยะเว้นพิเศษ)
    total_h = 0.0
    for ln in lines:
        total_h += ln["size"] * config.LINE_LEADING
        total_h += ln.get("gap_before", 0.0)

    # จุดเริ่ม (ขอบบนของบล็อก): จัดกลางแนวตั้ง หรือชิดบน
    if config.TEXT_VCENTER:
        center_y = (inner_top + inner_bottom) / 2.0
        block_top = center_y + total_h / 2.0
    else:
        block_top = inner_top

    cursor = block_top
    for ln in lines:
        cursor -= ln.get("gap_before", 0.0)
        cursor -= ln["size"] * config.LINE_LEADING   # เลื่อนลงหนึ่งช่องบรรทัด
        c.setFont(ln["font"], ln["size"])
        c.setFillColorRGB(*ln["color"])
        c.drawString(text_x, cursor, ln["text"])


def _draw_placeholder(c, x, y, w, h, label):
    """วาดกรอบว่างพร้อมข้อความ เมื่อไม่มีรูป/QR"""
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(0.5)
    c.rect(x, y, w, h, stroke=1, fill=0)
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawCentredString(x + w / 2, y + h / 2 - 3, label)


def generate_pdf(people, base_dir, output_path, photos_dir=None, qr_path=None):
    """
    people = list ของ dict [{thai_name, english_name, passport}, ...]
    วาง 8 คน/หน้า ขึ้นหน้าใหม่อัตโนมัติ แล้วบันทึกเป็น PDF ที่ output_path
    photos_dir: โฟลเดอร์รูปคน (ระบุเองได้ เช่น โฟลเดอร์ Google Drive ที่ sync)
    qr_path: ไฟล์ QR ของงานครั้งนี้ (ระบุเองได้ แต่ละครั้งใช้คนละอันได้)
    คืนค่า จำนวนใบที่สร้าง
    """
    register_fonts(base_dir)
    c = canvas.Canvas(output_path, pagesize=A4)
    page_w, page_h = A4

    tw = config.TAG_W_MM * mm
    th = config.TAG_H_MM * mm
    gx = config.GUTTER_X_MM * mm
    gy = config.GUTTER_Y_MM * mm

    grid_w = config.COLS * tw + (config.COLS - 1) * gx
    grid_h = config.ROWS * th + (config.ROWS - 1) * gy
    margin_x = (page_w - grid_w) / 2
    margin_y = (page_h - grid_h) / 2

    for i, person in enumerate(people):
        slot = i % config.TAGS_PER_PAGE
        if i > 0 and slot == 0:
            c.showPage()

        col = slot % config.COLS
        row = slot // config.COLS
        # แถวบนสุดอยู่ด้านบนของหน้า (row 0 = บนสุด)
        x = margin_x + col * (tw + gx)
        y = page_h - margin_y - (row + 1) * th - row * gy
        _draw_tag(c, x, y, person, base_dir, photos_dir, qr_path)

    c.showPage()
    c.save()
    return len(people)
