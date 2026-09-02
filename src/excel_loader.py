"""
อ่านข้อมูลผู้โดยสารจากไฟล์ Excel (.xlsx)
แถวแรก = หัวตาราง ต้องมีคอลัมน์: thai_name, english_name, passport
"""
import openpyxl

from . import config


REQUIRED_COLUMNS = [config.COL_THAI, config.COL_ENGLISH, config.COL_PASSPORT]


def load_people(xlsx_path):
    """
    คืนค่า (people, warnings)
    people = list ของ dict [{thai_name, english_name, passport}, ...]
    warnings = list ของข้อความเตือน (เช่น แถวที่ข้อมูลไม่ครบ)
    """
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("ไฟล์ Excel ว่างเปล่า")

    # หาตำแหน่งคอลัมน์จากหัวตาราง (แถวแรก)
    header = [str(h).strip().lower() if h is not None else "" for h in rows[0]]
    col_idx = {}
    for name in REQUIRED_COLUMNS:
        if name in header:
            col_idx[name] = header.index(name)
        else:
            raise ValueError(
                f"ไม่พบคอลัมน์ '{name}' ในไฟล์ Excel\n"
                f"หัวตารางต้องมี: {', '.join(REQUIRED_COLUMNS)}\n"
                f"พบ: {', '.join(h for h in header if h)}"
            )

    people = []
    warnings = []
    for r_num, row in enumerate(rows[1:], start=2):
        def cell(name):
            v = row[col_idx[name]] if col_idx[name] < len(row) else None
            return "" if v is None else str(v).strip()

        thai = cell(config.COL_THAI)
        eng = cell(config.COL_ENGLISH)
        passport = cell(config.COL_PASSPORT)

        # ข้ามแถวว่างทั้งแถว
        if not any([thai, eng, passport]):
            continue

        if not passport:
            warnings.append(f"แถว {r_num}: ไม่มีเลขพาสปอร์ต (จะหารูปไม่เจอ)")

        people.append({
            config.COL_THAI: thai,
            config.COL_ENGLISH: eng,
            config.COL_PASSPORT: passport,
        })

    return people, warnings
