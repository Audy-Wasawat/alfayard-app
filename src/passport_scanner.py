# -*- coding: utf-8 -*-
"""
passport_scanner.py
อ่านรูปหน้าพาสปอร์ต แล้วดึง: ชื่อไทย, ชื่ออังกฤษ, เลขพาสปอร์ต

โหมดการอ่าน (เลือกได้):
  - "free"  : ออฟไลน์/ฟรี  → Tesseract OCR + parser แถบ MRZ (เขียนเอง ไม่พึ่ง lib หนัก)
  - "claude": ใช้ Claude Vision API (แม่นที่สุด, ต้องมี ANTHROPIC_API_KEY)

โหมดฟรีต้องการแค่:  Tesseract (โปรแกรม) + pytesseract + Pillow
  ไม่ต้องติดตั้ง scipy / scikit-image / passporteye ที่หนักและติดตั้งยาก

หลักการโหมดฟรี:
  * แถบ MRZ = 2 บรรทัดล่างสุดของพาสปอร์ต เป็นมาตรฐานสากล TD3 (บรรทัดละ 44 ตัว)
    อ่านง่ายและแม่น เพราะเป็นตัวพิมพ์ใหญ่ระยะเท่ากัน → ได้ชื่ออังกฤษ + เลขพาสปอร์ต
  * ชื่อไทย อ่านจากส่วนบนด้วย Tesseract ภาษาไทย
"""

import os
import re
import unicodedata

try:
    from PIL import Image, ImageOps, ImageFilter
    HAS_PIL = True
except Exception:
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESS = True
except Exception:
    HAS_TESS = False


def _autodetect_tesseract():
    """
    หา tesseract.exe อัตโนมัติ (โดยเฉพาะบน Windows ที่ installer มักไม่ใส่ PATH)
    ถ้าเจอจะตั้งค่าให้ pytesseract ใช้ path นั้นเอง

    ตั้งค่าเองได้ผ่าน environment variable  TESSERACT_CMD  (path เต็มของ tesseract.exe)
    """
    if not HAS_TESS:
        return
    import shutil
    import platform
    import glob

    # 0) ผู้ใช้กำหนดเองผ่าน env var
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd and os.path.isfile(env_cmd):
        pytesseract.pytesseract.tesseract_cmd = env_cmd
        return

    # 1) ถ้ามีใน PATH อยู่แล้ว ใช้เลย
    if shutil.which("tesseract"):
        return

    candidates = []
    if platform.system() == "Windows":
        # โฟลเดอร์ฐานที่ installer (UB Mannheim) นิยมลง ทั้งแบบ all-users และ per-user
        bases = [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
            os.environ.get("APPDATA", ""),
            os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Programs"),
            r"C:\\",
            r"D:\\",
        ]
        for base in bases:
            if base:
                candidates.append(os.path.join(base, "Tesseract-OCR", "tesseract.exe"))
        # ค้นแบบกวาด (เผื่อชื่อโฟลเดอร์เพี้ยน) — จำกัดเฉพาะที่นิยม กันช้า
        for base in bases:
            if base and os.path.isdir(base):
                candidates += glob.glob(os.path.join(base, "*esseract*", "tesseract.exe"))
    else:  # macOS / Linux
        candidates += ["/opt/homebrew/bin/tesseract",  # Mac (Apple Silicon)
                       "/usr/local/bin/tesseract",       # Mac (Intel)
                       "/usr/bin/tesseract"]

    for c in candidates:
        if c and os.path.isfile(c):
            pytesseract.pytesseract.tesseract_cmd = c
            return


_autodetect_tesseract()


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

TITLE_BY_SEX = {"M": "MR", "F": "MS"}
THAI_TITLE_BY_SEX = {"M": "นาย", "F": "นางสาว"}


# =========================================================
#   ยูทิลิตี้
# =========================================================
def list_images(folder):
    files = []
    for name in sorted(os.listdir(folder)):
        if os.path.splitext(name)[1].lower() in IMAGE_EXTS:
            files.append(os.path.join(folder, name))
    return files


def _clean(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"\s+", " ", s).strip()


def _title_case_en(s):
    out = []
    for p in s.split():
        if p.upper() in ("II", "III", "IV"):
            out.append(p.upper())
        else:
            out.append(p.capitalize())
    return " ".join(out)


def _open_image(path):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)   # หมุนตาม EXIF (รูปมือถือ)
    return img


# =========================================================
#   ค่าคงที่
# =========================================================
MRZ_CFG = ("--psm 6 -c tessedit_char_whitelist="
           "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")
TITLE_EN = {"MR": "Mr.", "MRS": "Mrs.", "MISS": "Miss", "MS": "Ms.",
            "MASTER": "Master", "MSTR": "Master"}
TITLE_TH = {"MR": "นาย", "MRS": "นาง", "MISS": "นางสาว", "MS": "นางสาว",
            "MASTER": "เด็กชาย", "MSTR": "เด็กชาย"}
# อักษรนำหน้าเดือน (กันสับสนกับเลขพาสปอร์ตตอน regex)
_MONTH2 = {"JA", "FE", "MA", "AP", "MY", "JU", "AU", "SE", "OC", "NO", "DE"}


def _prep_page(img):
    """เตรียมภาพทั้งหน้า (grayscale + autocontrast + ขยายให้กว้าง ~1600)"""
    g = ImageOps.autocontrast(img.convert("L"))
    w, h = g.size
    if w < 1600:
        s = 1600 / w
        g = g.resize((int(w * s), int(h * s)))
    return g


# =========================================================
#   MRZ (แถบ 2 บรรทัดล่าง) — เอานามสกุล + เพศ + เลขพาสปอร์ตสำรอง
# =========================================================
def read_mrz(img):
    """คืน dict: surname, given, sex, passport (จาก MRZ TD3)"""
    out = {"surname": "", "given": "", "sex": "", "passport": ""}
    if not (HAS_TESS and HAS_PIL):
        return out
    g = ImageOps.autocontrast(img.convert("L"))
    w, h = g.size
    crop = g.crop((0, int(h * 0.55), w, h))       # โซนล่าง ~45%
    cw, ch = crop.size
    s = max(1.0, 2000 / cw)                         # ขยายให้ MRZ คม
    crop = crop.resize((int(cw * s), int(ch * s)))
    try:
        txt = pytesseract.image_to_string(crop, lang="eng", config=MRZ_CFG)
    except Exception:
        return out

    cleaned = [re.sub(r"[^A-Z0-9<]", "", x.upper()) for x in txt.splitlines()]
    cleaned = [c for c in cleaned if len(c) >= 30]
    l1 = l2 = None
    for i, c in enumerate(cleaned):
        if c.startswith("P") and "<<" in c:        # บรรทัด 1 = P<XXX<surname<<given
            l1 = c
            for j in range(i + 1, len(cleaned)):    # บรรทัด 2 = passport+ตัวเลข
                if re.match(r"^[A-Z0-9<]{9}[0-9<]", cleaned[j]):
                    l2 = cleaned[j]
                    break
            break

    if l1:
        body = l1[5:]                               # ตัด P<THA
        surname = body.split("<")[0]                # นามสกุล = ก่อน < ตัวแรก
        out["surname"] = "".join(ch for ch in surname if ch.isalpha())
        rest = body[len(surname):].lstrip("<")
        given = rest.split("<")[0]
        out["given"] = "".join(ch for ch in given if ch.isalpha())
    if l2:
        if len(l2) > 20 and l2[20] in "MF":
            out["sex"] = l2[20]
        cand = l2[0:9].replace("<", "")
        if re.match(r"^[A-Z]{1,2}\d{6,7}$", cand):
            out["passport"] = cand
    return out


# =========================================================
#   หน้าข้อมูล (พิมพ์ชัด) — เลขพาสปอร์ต + คำนำหน้า/ชื่ออังกฤษ
# =========================================================
def _find_passport(txt):
    """เลขพาสปอร์ตไทย = อักษร 1-2 ตัว + เลข 7 ตัว ติดกัน (ไม่ใช่ตัวย่อเดือน)"""
    for m in re.finditer(r"\b([A-Z]{1,2})(\d{7})\b", txt):
        if m.group(1) not in _MONTH2:
            return m.group(0)
    return ""


def _find_title_given(txt):
    """หาแถว 'MR./MRS./MISS/MS ชื่อ' บนหน้าข้อมูล → (title, given)"""
    for line in txt.splitlines():
        u = line.upper().strip()
        if "THAILAND" in u:
            continue
        m = re.search(r"\b(MASTER|MSTR|MRS|MISS|MR|MS)\.?\s+([A-Z]{2,}(?:\s+[A-Z]{2,})*)", u)
        if m:
            return m.group(1), m.group(2).strip()
    return "", ""


def _find_surname(txt):
    """ดึงนามสกุลอังกฤษจากช่อง 'Surname' บนหน้าข้อมูล (สะอาดกว่า MRZ)"""
    lines = txt.splitlines()
    for i, l in enumerate(lines):
        if re.search(r"Surname", l, re.I):
            # ค่านามสกุลมักอยู่บรรทัดถัดไป (ตัวพิมพ์ใหญ่ล้วน)
            for j in range(i + 1, min(i + 3, len(lines))):
                cands = [w for w in re.findall(r"\b[A-Z]{3,}\b", lines[j])
                         if w not in ("SURNAME", "NAME", "TITLE", "THA", "THAI")]
                if cands:
                    return cands[0]
            break
    return ""


_THAI_TITLE_RE = re.compile(
    r"(นางสาว|นาง|นาย|น\s*[.,]?\s*ส|ด\s*[.,]?\s*ช|ด\s*[.,]?\s*ญ|เด็กชาย|เด็กหญิง)"
    r"[.,\s]*([ก-๙][ก-๙\s]{1,40})"
)
# คำที่เป็น 'ป้ายกำกับ' บนพาสปอร์ต — ถ้าเจอในบรรทัดให้ข้าม (กันดึงป้ายมาปน)
_THAI_LABELS = ("สัญชาติ", "วันเกิด", "ประจําตัว", "ประจำตัว", "ประชาชน",
                "ประเทศ", "ออกให้", "สถานที่", "ส่วนสูง", "นามสกุล",
                "หนังสือเดินทาง", "ลายมือ", "หมดอายุ", "รหัส")


def _find_thai_name(txt, en_title=""):
    """หาแถวชื่อไทย (คำนำหน้า + ชื่อ-สกุล) จากผล OCR ภาษาไทย"""
    for line in txt.splitlines():
        t = re.sub(r"\s+", " ", line).strip()
        if any(lb in t for lb in _THAI_LABELS):
            continue
        m = _THAI_TITLE_RE.search(t)
        if m:
            name = re.sub(r"\s+", " ", m.group(2)).strip()
            if len(name) < 2:
                continue
            rt = m.group(1)
            if rt in ("นาย", "นาง", "นางสาว", "เด็กชาย", "เด็กหญิง"):
                th_title = rt
            elif rt.startswith("น"):
                th_title = "นางสาว"          # น.ส.
            elif rt.startswith("ด") and "ช" in rt:
                th_title = "เด็กชาย"          # ด.ช.
            elif rt.startswith("ด") and "ญ" in rt:
                th_title = "เด็กหญิง"          # ด.ญ.
            else:
                th_title = rt
            if not th_title:
                th_title = TITLE_TH.get(en_title, "")
            return f"{th_title} {name}".strip()
    return ""


# =========================================================
#   โหมดฟรี: รวมผล (หน้าข้อมูล + MRZ)
# =========================================================
def scan_free(image_path):
    result = {"thai_name": "", "english_name": "", "passport": "",
              "source": "OCR", "note": ""}
    if not (HAS_TESS and HAS_PIL):
        result["note"] = "ไม่พบ Tesseract/Pillow"
        return result
    try:
        img = _open_image(image_path)
    except Exception as e:
        result["note"] = f"เปิดรูปไม่ได้: {e}"
        return result

    page = _prep_page(img)
    try:
        txt_en = pytesseract.image_to_string(page, lang="eng", config="--psm 4")
    except Exception:
        txt_en = ""
    try:
        txt_th = pytesseract.image_to_string(page, lang="tha", config="--psm 4")
    except Exception:
        txt_th = ""

    mrz = read_mrz(img)

    # เลขพาสปอร์ต: หน้าข้อมูลก่อน แล้วค่อย MRZ
    passport = _find_passport(txt_en) or mrz["passport"]

    # ชื่ออังกฤษ: คำนำหน้า+ชื่อ จากหน้าข้อมูล, นามสกุลจากหน้าข้อมูลก่อน แล้วค่อย MRZ
    title, given = _find_title_given(txt_en)
    if not given:
        given = mrz["given"]
    surname = _find_surname(txt_en) or mrz["surname"]
    english = ""
    if given or surname:
        english = " ".join(p for p in [TITLE_EN.get(title, ""),
                                       given.title(), surname.title()] if p)

    # ชื่อไทย
    thai = _find_thai_name(txt_th, en_title=title)

    notes = []
    if not passport:
        notes.append("อ่านเลขพาสปอร์ตไม่ได้")
    if not english:
        notes.append("อ่านชื่ออังกฤษไม่ได้")
    if not thai:
        notes.append("อ่านชื่อไทยไม่ได้")

    result.update({"thai_name": thai, "english_name": english,
                   "passport": passport, "note": ", ".join(notes)})
    return result


# =========================================================
#   โหมด Claude Vision (ออปชั่นเสริม)
# =========================================================
def scan_claude(image_path, api_key=None, model="claude-3-5-sonnet-20241022"):
    import base64
    import io
    import json
    try:
        import anthropic
    except Exception:
        return {"thai_name": "", "english_name": "", "passport": "",
                "source": "claude", "note": "ยังไม่ได้ติดตั้ง anthropic (pip install anthropic)"}

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"thai_name": "", "english_name": "", "passport": "",
                "source": "claude", "note": "ไม่พบ ANTHROPIC_API_KEY"}

    if HAS_PIL:
        img = _open_image(image_path).convert("RGB")
        w, h = img.size
        if max(w, h) > 2000:
            s = 2000 / max(w, h)
            img = img.resize((int(w * s), int(h * s)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        raw = buf.getvalue()
    else:
        with open(image_path, "rb") as f:
            raw = f.read()
    b64 = base64.standard_b64encode(raw).decode("utf-8")

    prompt = (
        "นี่คือรูปหน้าพาสปอร์ต ช่วยดึงข้อมูล 3 อย่างและตอบกลับเป็น JSON เท่านั้น "
        "ห้ามมีข้อความอื่น: "
        '{"thai_name": "ชื่อไทยพร้อมคำนำหน้า", '
        '"english_name": "ชื่ออังกฤษ Title Case เช่น Mr. Somchai Jaidee", '
        '"passport": "เลขพาสปอร์ต"} ถ้าอ่านช่องไหนไม่ได้ให้ใส่ค่าว่าง'
    )
    client = anthropic.Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model=model, max_tokens=400,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": prompt}]}])
        text = msg.content[0].text.strip()
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else {}
    except Exception as e:
        return {"thai_name": "", "english_name": "", "passport": "",
                "source": "claude", "note": f"เรียก API ไม่สำเร็จ: {e}"}

    thai = _clean(data.get("thai_name", ""))
    english = _clean(data.get("english_name", ""))
    passport = _clean(data.get("passport", "")).upper()
    notes = []
    if not passport:
        notes.append("อ่านเลขพาสปอร์ตไม่ได้")
    if not english:
        notes.append("อ่านชื่ออังกฤษไม่ได้")
    if not thai:
        notes.append("อ่านชื่อไทยไม่ได้")
    return {"thai_name": thai, "english_name": english, "passport": passport,
            "source": "claude", "note": ", ".join(notes)}


# =========================================================
#   โหมด Gemini (Google) — ฟรีเทียร์ อ่านรูปได้
# =========================================================
GEMINI_KEY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "gemini_api_key.txt")


def load_gemini_key(explicit=None):
    """หา Gemini API key: อาร์กิวเมนต์ > env GEMINI_API_KEY/GOOGLE_API_KEY > ไฟล์ gemini_api_key.txt"""
    if explicit and explicit.strip():
        return explicit.strip()
    env = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env and env.strip():
        return env.strip()
    try:
        if os.path.isfile(GEMINI_KEY_FILE):
            with open(GEMINI_KEY_FILE, "r", encoding="utf-8") as f:
                k = f.read().strip()
                if k:
                    return k
    except Exception:
        pass
    return ""


def save_gemini_key(key):
    """บันทึก key ลงไฟล์ในโปรเจกต์ (ควร gitignore) เพื่อไม่ต้องกรอกซ้ำทุกครั้ง"""
    try:
        with open(GEMINI_KEY_FILE, "w", encoding="utf-8") as f:
            f.write((key or "").strip())
        return True
    except Exception:
        return False


def scan_gemini(image_path, api_key=None, model="gemini-2.0-flash"):
    """อ่านหน้าพาสปอร์ตด้วย Google Gemini (vision) — ฟรีเทียร์"""
    import json
    key = load_gemini_key(api_key)
    if not key:
        return {"thai_name": "", "english_name": "", "passport": "",
                "source": "gemini", "note": "ไม่พบ Gemini API key"}
    try:
        import google.generativeai as genai
    except Exception:
        return {"thai_name": "", "english_name": "", "passport": "",
                "source": "gemini",
                "note": "ยังไม่ได้ติดตั้ง google-generativeai (pip install google-generativeai)"}

    if HAS_PIL:
        try:
            img = _open_image(image_path).convert("RGB")
        except Exception as e:
            return {"thai_name": "", "english_name": "", "passport": "",
                    "source": "gemini", "note": f"เปิดรูปไม่ได้: {e}"}
        w, h = img.size
        if max(w, h) > 2000:
            s = 2000 / max(w, h)
            img = img.resize((int(w * s), int(h * s)))
    else:
        img = None

    prompt = (
        "นี่คือรูปหน้าพาสปอร์ต (ไทยหรือต่างชาติ) ช่วยดึงข้อมูล 3 อย่าง "
        "แล้วตอบกลับเป็น JSON เท่านั้น ห้ามมีข้อความอื่นหรือ markdown fence: "
        '{"thai_name": "ชื่อไทยพร้อมคำนำหน้า เช่น นาย สมชาย ใจดี", '
        '"english_name": "ชื่ออังกฤษ Title Case เช่น Mr. Somchai Jaidee", '
        '"passport": "เลขพาสปอร์ต เช่น AA1234567"} '
        "กติกา: คำนำหน้าไทยใช้ นาย/นาง/นางสาว/เด็กชาย/เด็กหญิง ให้ตรงเพศและอายุ; "
        "ถ้าเป็นพาสปอร์ตต่างชาติ (ไม่มีชื่อไทย) ให้ thai_name เป็นค่าว่าง; "
        "เลขพาสปอร์ตอ่านจากหน้าข้อมูลเป็นหลัก (รูปแบบอักษร 1-2 ตัวตามด้วยเลข); "
        "ถ้าช่องไหนอ่านไม่ได้ให้ใส่ค่าว่าง"
    )
    # ลองหลายชื่อโมเดล เผื่อบางตัวถูกเปลี่ยน/ปิด (ตัวแรกที่ผู้เรียกส่งมาก่อน)
    candidates = [model, "gemini-2.0-flash", "gemini-2.5-flash",
                  "gemini-flash-latest", "gemini-1.5-flash"]
    seen = set()
    candidates = [c for c in candidates if c and not (c in seen or seen.add(c))]
    content = [prompt, img] if img is not None else [prompt]
    genai.configure(api_key=key)
    data = None
    last_err = ""
    for mdl in candidates:
        try:
            gm = genai.GenerativeModel(mdl)
            resp = gm.generate_content(content)
            text = (getattr(resp, "text", "") or "").strip()
            m = re.search(r"\{.*\}", text, re.S)
            data = json.loads(m.group(0)) if m else {}
            break
        except Exception as e:
            last_err = f"{mdl}: {e}"
            continue
    if data is None:
        return {"thai_name": "", "english_name": "", "passport": "",
                "source": "gemini", "note": f"เรียก Gemini ไม่สำเร็จ: {last_err}"}

    thai = _clean(data.get("thai_name", ""))
    english = _clean(data.get("english_name", ""))
    passport = _clean(data.get("passport", "")).upper().replace(" ", "")
    notes = []
    if not passport:
        notes.append("อ่านเลขพาสปอร์ตไม่ได้")
    if not english:
        notes.append("อ่านชื่ออังกฤษไม่ได้")
    if not thai:
        notes.append("อ่านชื่อไทยไม่ได้")
    return {"thai_name": thai, "english_name": english, "passport": passport,
            "source": "gemini", "note": ", ".join(notes)}


def scan_auto(image_path, api_key=None):
    """โหมดผสม: Tesseract ฟรีก่อน ถ้าช่องไหนขาด เรียก Gemini มาเติมเฉพาะช่องที่ขาด"""
    res = scan_free(image_path)
    missing = (not res.get("thai_name") or not res.get("english_name")
               or not res.get("passport"))
    if not missing:
        res["source"] = "OCR"
        return res

    g = scan_gemini(image_path, api_key=api_key)
    gnote = g.get("note", "")
    if gnote.startswith("ยังไม่ได้ติดตั้ง") or "ไม่พบ Gemini API key" in gnote:
        res["note"] = (res.get("note", "") + " | Gemini: " + gnote).strip(" |")
        return res

    used = []
    for field in ("thai_name", "english_name", "passport"):
        if not res.get(field) and g.get(field):
            res[field] = g[field]
            used.append(field)

    notes = []
    if not res.get("passport"):
        notes.append("อ่านเลขพาสปอร์ตไม่ได้")
    if not res.get("english_name"):
        notes.append("อ่านชื่ออังกฤษไม่ได้")
    if not res.get("thai_name"):
        notes.append("อ่านชื่อไทยไม่ได้")
    res["note"] = ", ".join(notes)
    res["source"] = "OCR+Gemini" if used else "OCR"
    return res



# =========================================================
#   ตัวเรียกหลัก
# =========================================================
def scan_image(image_path, mode="free", api_key=None):
    if mode == "claude":
        res = scan_claude(image_path, api_key=api_key)
    elif mode == "gemini":
        res = scan_gemini(image_path, api_key=api_key)
    elif mode == "auto":
        res = scan_auto(image_path, api_key=api_key)
    else:
        res = scan_free(image_path)
    res["file"] = os.path.basename(image_path)
    return res


def scan_folder(folder, mode="free", api_key=None, progress=None):
    images = list_images(folder)
    rows = []
    total = len(images)
    for i, path in enumerate(images, 1):
        if progress:
            progress(i, total, os.path.basename(path))
        rows.append(scan_image(path, mode=mode, api_key=api_key))
    return rows


def tesseract_path():
    """path ของ tesseract ที่โปรแกรมจะใช้ (ไว้แสดง/debug)"""
    if not HAS_TESS:
        return ""
    import shutil
    cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
    if cmd and cmd != "tesseract" and os.path.isfile(cmd):
        return cmd
    found = shutil.which(cmd) or shutil.which("tesseract")
    return found or ""


def _tesseract_works():
    """เช็กว่าเรียก tesseract ได้จริง (ไม่ใช่แค่เจอไฟล์)"""
    if not HAS_TESS:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def capabilities():
    tess_ok = _tesseract_works()
    tess_lang = ""
    if tess_ok:
        try:
            tess_lang = ",".join(pytesseract.get_languages(config=""))
        except Exception:
            tess_lang = "?"
    return {
        "Pillow": HAS_PIL,
        "Tesseract": tess_ok,
        "ภาษาไทย(tha)": ("tha" in tess_lang) if tess_lang else False,
    }
