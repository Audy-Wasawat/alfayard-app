"""
จัดการรูปคน: crop รูปต้นฉบับ (สัดส่วนใดก็ได้) ให้พอดีกรอบที่กำหนด
โดยจัดกึ่งกลางแล้วตัดส่วนเกิน (center-crop) — รูปทุกใบจึงได้ขนาด/สัดส่วนเท่ากัน
"""
import os
from PIL import Image, ImageOps

from . import config


def find_photo_path(passport, base_dir, photos_dir=None):
    """
    หาไฟล์รูปจากเลขพาสปอร์ต เช่น AA1234567.jpg
    photos_dir: ระบุโฟลเดอร์รูปเองได้ (เช่น โฟลเดอร์ Google Drive ที่ sync ลงเครื่อง)
                ถ้าไม่ระบุ ใช้โฟลเดอร์ photos/ ในโปรเจกต์
    """
    if photos_dir:
        search_dir = photos_dir
    else:
        search_dir = os.path.join(base_dir, config.PHOTOS_DIR)
    for ext in config.PHOTO_EXTENSIONS:
        candidate = os.path.join(search_dir, f"{passport}{ext}")
        if os.path.exists(candidate):
            return candidate
    return None


def crop_to_box(img, target_w_px, target_h_px):
    """
    center-crop รูปให้ได้อัตราส่วน target แล้ว resize เป็นขนาด target พอดี
    ไม่ยืด/บิดรูป — ตัดส่วนเกินออกเท่านั้น
    """
    # ImageOps.fit ทำ center-crop + resize ในขั้นตอนเดียว
    return ImageOps.fit(
        img,
        (target_w_px, target_h_px),
        method=Image.LANCZOS,
        centering=(0.5, 0.5),
    )


def prepare_photo(src_path, target_w_mm, target_h_mm, dpi=300):
    """
    เปิดรูปต้นฉบับ แก้ orientation ตาม EXIF, แปลงเป็น RGB,
    center-crop ให้พอดีกรอบ แล้วคืนค่าเป็น PIL.Image พร้อมฝังใน PDF
    """
    img = Image.open(src_path)
    img = ImageOps.exif_transpose(img)   # หมุนตามข้อมูล EXIF (รูปจากมือถือ)
    if img.mode != "RGB":
        img = img.convert("RGB")

    target_w_px = max(1, int(round(target_w_mm / 25.4 * dpi)))
    target_h_px = max(1, int(round(target_h_mm / 25.4 * dpi)))
    return crop_to_box(img, target_w_px, target_h_px)
