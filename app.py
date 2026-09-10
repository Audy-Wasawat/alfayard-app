#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — โปรแกรมรวม: สแกนพาสปอร์ต + สร้างใบติดกระเป๋า (Alfayard 1441)

เปิดโปรแกรมเดียว ได้ 2 แท็บในหน้าต่างเดียว:
  แท็บ 1) สแกนพาสปอร์ต  → สร้าง passengers.xlsx (ฟรี Tesseract / เติมด้วย Gemini)
  แท็บ 2) สร้างใบติดกระเป๋า → เลือก Excel + โฟลเดอร์รูป → ได้ PDF 8 ใบ/หน้า

พอสแกนเสร็จในแท็บ 1 ไฟล์ Excel จะถูกส่งต่อให้แท็บ 2 อัตโนมัติ

รัน:  python app.py   (หรือดับเบิลคลิก START.bat บน Windows)
"""
import os
import sys
import threading
import traceback
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)                       # ให้ import แพ็กเกจ src.* ได้ (ใบติดกระเป๋า)
sys.path.insert(0, os.path.join(BASE_DIR, "src"))  # ให้ import โมดูลสแกน (passport_scanner, excel_export)

# --- โมดูลฝั่งสแกนพาสปอร์ต (absolute import จาก src/) ---
from passport_scanner import (scan_folder, list_images, capabilities,   # noqa
                              tesseract_path, load_gemini_key, save_gemini_key)
from excel_export import export_excel  # noqa

# --- โมดูลฝั่งใบติดกระเป๋า (แพ็กเกจ src) ---
from src.excel_loader import load_people          # noqa
from src.generator import generate_pdf            # noqa
from src.passport_label import generate_passport_labels  # noqa
from src.photo_sheet import generate_photo_sheet  # noqa
from src.photo import find_photo_path             # noqa
from src import config                            # noqa


# =========================================================
#   แท็บ 1: สแกนพาสปอร์ต → Excel
# =========================================================
class ScanTab(ttk.Frame):
    def __init__(self, master, on_excel_ready=None):
        super().__init__(master)
        self.on_excel_ready = on_excel_ready   # callback(path) เมื่อสแกนเสร็จ

        self.folder = tk.StringVar()
        self.output = tk.StringVar(value=os.path.join(BASE_DIR, "passengers.xlsx"))
        self.mode = tk.StringVar(value="auto")
        self.review = tk.BooleanVar(value=True)
        self.api_key = tk.StringVar(value=load_gemini_key())

        self._build()

    def _build(self):
        pad = {"padx": 12, "pady": 5}
        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=8, pady=8)

        ttk.Label(frm, text="1) โฟลเดอร์รูปหน้าพาสปอร์ต", font=("", 11, "bold")).pack(anchor="w")
        row = ttk.Frame(frm); row.pack(fill="x", **pad)
        ttk.Entry(row, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="เลือก...", command=self._pick_folder).pack(side="left", padx=6)

        ttk.Label(frm, text="2) โหมดการอ่าน", font=("", 11, "bold")).pack(anchor="w")
        mrow = ttk.Frame(frm); mrow.pack(fill="x", **pad)
        ttk.Radiobutton(mrow, text="ฟรี / ออฟไลน์  (Tesseract + MRZ — ไม่ใช้เน็ต)",
                        variable=self.mode, value="free", command=self._toggle_api).pack(anchor="w")
        ttk.Radiobutton(mrow, text="ฟรี + Gemini เติมช่องที่ขาด  (แนะนำ)",
                        variable=self.mode, value="auto", command=self._toggle_api).pack(anchor="w")
        ttk.Radiobutton(mrow, text="Gemini ล้วน  (แม่นสุดกับรูปเอียง/แสงสะท้อน)",
                        variable=self.mode, value="gemini", command=self._toggle_api).pack(anchor="w")

        self.api_frame = ttk.Frame(frm)
        ttk.Label(self.api_frame, text="Gemini API key:").pack(side="left")
        ttk.Entry(self.api_frame, textvariable=self.api_key, show="*", width=40).pack(side="left", padx=6)
        ttk.Label(self.api_frame, text="(ขอฟรีที่ aistudio.google.com)", foreground="#888").pack(side="left")

        ttk.Label(frm, text="3) ไฟล์ผลลัพธ์ (.xlsx)", font=("", 11, "bold")).pack(anchor="w")
        orow = ttk.Frame(frm); orow.pack(fill="x", **pad)
        ttk.Entry(orow, textvariable=self.output).pack(side="left", fill="x", expand=True)
        ttk.Button(orow, text="บันทึกเป็น...", command=self._pick_output).pack(side="left", padx=6)

        ttk.Checkbutton(frm, text="โหมดตรวจทาน (เพิ่มคอลัมน์ note/source/file + ไฮไลต์แถวที่อ่านไม่ครบ)",
                        variable=self.review).pack(anchor="w", pady=3)

        self.btn = ttk.Button(frm, text="เริ่มสแกน", command=self._start)
        self.btn.pack(pady=6)
        self.prog = ttk.Progressbar(frm, mode="determinate")
        self.prog.pack(fill="x", pady=3)
        self.log = tk.Text(frm, height=7)
        self.log.pack(fill="both", expand=True, pady=3)

        caps = capabilities()
        status = "  ".join(f"{k}:{'OK' if v else 'X'}" for k, v in caps.items())
        ttk.Label(frm, text="เครื่องมือ: " + status, foreground="#555").pack(anchor="w")
        ttk.Label(frm, text="Tesseract: " + (tesseract_path() or "(ไม่พบ — ตั้ง env TESSERACT_CMD)"),
                  foreground="#888").pack(anchor="w")

        self._toggle_api()

    def _toggle_api(self):
        if self.mode.get() in ("auto", "gemini"):
            self.api_frame.pack(fill="x", padx=12, pady=3, before=self.btn)
        else:
            self.api_frame.pack_forget()

    def _pick_folder(self):
        d = filedialog.askdirectory(title="เลือกโฟลเดอร์รูปพาสปอร์ต")
        if d:
            self.folder.set(d)

    def _pick_output(self):
        f = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                         filetypes=[("Excel", "*.xlsx")],
                                         initialfile="passengers.xlsx", initialdir=BASE_DIR)
        if f:
            self.output.set(f)

    def _write_log(self, msg):
        self.log.insert("end", msg + "\n"); self.log.see("end"); self.update_idletasks()

    def _start(self):
        folder = self.folder.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("ผิดพลาด", "กรุณาเลือกโฟลเดอร์รูปให้ถูกต้อง"); return
        if self.mode.get() in ("auto", "gemini") and not self.api_key.get().strip():
            messagebox.showerror("ผิดพลาด", "โหมดนี้ต้องใส่ Gemini API key\n(ขอฟรีที่ aistudio.google.com)"); return
        if self.api_key.get().strip():
            save_gemini_key(self.api_key.get().strip())
        images = list_images(folder)
        if not images:
            messagebox.showwarning("แจ้ง", "ไม่พบไฟล์รูปในโฟลเดอร์นี้"); return

        self.btn.config(state="disabled")
        self.log.delete("1.0", "end")
        self.prog["maximum"] = len(images); self.prog["value"] = 0
        self._write_log(f"พบรูป {len(images)} ไฟล์ — เริ่มสแกน (โหมด {self.mode.get()})")
        threading.Thread(target=self._run, args=(folder, images), daemon=True).start()

    def _run(self, folder, images):
        def progress(i, total, name):
            self.prog["value"] = i; self._write_log(f"[{i}/{total}] {name}")
        try:
            rows = scan_folder(folder, mode=self.mode.get(),
                               api_key=self.api_key.get().strip() or None, progress=progress)
            out = export_excel(rows, self.output.get(), review=self.review.get())
            ok = sum(1 for r in rows if r.get("thai_name") and r.get("english_name") and r.get("passport"))
            self._write_log(f"\nเสร็จ: อ่านครบ {ok}/{len(rows)} ราย")
            if ok < len(rows):
                self._write_log("แถวที่อ่านไม่ครบถูกไฮไลต์สีเหลือง — ตรวจแก้ในไฟล์ได้")
            self._write_log(f"บันทึก: {os.path.abspath(out)}")
            # ส่งต่อไฟล์ให้แท็บใบติดกระเป๋า
            if self.on_excel_ready:
                self.on_excel_ready(os.path.abspath(out))
            messagebox.showinfo("สำเร็จ",
                f"บันทึกไฟล์แล้ว:\n{os.path.abspath(out)}\n\nอ่านครบ {ok}/{len(rows)} ราย\n\n"
                f"ส่งไฟล์ให้แท็บ 'สร้างใบติดกระเป๋า' แล้ว")
        except Exception as e:
            self._write_log(f"[ผิดพลาด] {e}")
            messagebox.showerror("ผิดพลาด", str(e))
        finally:
            self.btn.config(state="normal")


# =========================================================
#   แท็บ 2: สร้างใบติดกระเป๋า → PDF
# =========================================================
class TagTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.xlsx_path = tk.StringVar(value=self._default_xlsx())
        self.photos_dir = tk.StringVar(value=os.path.join(BASE_DIR, config.PHOTOS_DIR))
        self.qr_path = tk.StringVar(value="")   # เริ่มว่างเสมอ — ใส่ QR เฉพาะเมื่อกด "เลือก..." เอง
        self.people = []
        self._build()
        if os.path.exists(self.xlsx_path.get()):
            self.reload()

    def _default_xlsx(self):
        p = os.path.join(BASE_DIR, "passengers.xlsx")
        return p if os.path.exists(p) else ""

    def _default_qr(self):
        p = os.path.join(BASE_DIR, config.QR_IMAGE)
        return p if os.path.exists(p) else ""

    def _build(self):
        pad = {"padx": 10, "pady": 5}
        top = ttk.Frame(self); top.pack(fill="x", **pad)
        ttk.Label(top, text="ไฟล์ Excel:", width=11).pack(side="left")
        ttk.Entry(top, textvariable=self.xlsx_path).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="เลือก...", command=self.browse).pack(side="left")
        ttk.Button(top, text="โหลดใหม่", command=self.reload).pack(side="left", padx=4)

        prow = ttk.Frame(self); prow.pack(fill="x", padx=10)
        ttk.Label(prow, text="โฟลเดอร์รูป:", width=11).pack(side="left")
        ttk.Entry(prow, textvariable=self.photos_dir).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(prow, text="เลือก...", command=self.browse_photos).pack(side="left")

        qrow = ttk.Frame(self); qrow.pack(fill="x", padx=10, pady=5)
        ttk.Label(qrow, text="ไฟล์ QR:", width=11).pack(side="left")
        ttk.Entry(qrow, textvariable=self.qr_path).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(qrow, text="เลือก...", command=self.browse_qr).pack(side="left")

        mid = ttk.Frame(self); mid.pack(fill="both", expand=True, **pad)
        cols = ("no", "thai", "english", "passport", "photo")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=11)
        for c, txt, w in [("no", "#", 40), ("thai", "ชื่อไทย", 175),
                          ("english", "ชื่ออังกฤษ", 175), ("passport", "พาสปอร์ต", 100),
                          ("photo", "รูป", 55)]:
            self.tree.heading(c, text=txt); self.tree.column(c, width=w, anchor="w")
        self.tree.column("no", anchor="center"); self.tree.column("photo", anchor="center")
        vsb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True); vsb.pack(side="right", fill="y")
        self.tree.tag_configure("missing", foreground="#c0392b")

        bottom = ttk.Frame(self); bottom.pack(fill="x", **pad)
        self.status = tk.StringVar(value="ยังไม่ได้โหลดข้อมูล")
        ttk.Label(bottom, textvariable=self.status).pack(side="left")
        ttk.Button(bottom, text="สร้าง PDF", command=self.generate).pack(side="right")

    def set_excel(self, path):
        """เรียกจากแท็บสแกน: ตั้งไฟล์ Excel ใหม่แล้วโหลดตาราง"""
        self.xlsx_path.set(path)
        self.reload()

    def browse(self):
        p = filedialog.askopenfilename(title="เลือกไฟล์ Excel",
                                       filetypes=[("Excel", "*.xlsx"), ("ทุกไฟล์", "*.*")], initialdir=BASE_DIR)
        if p:
            self.xlsx_path.set(p); self.reload()

    def browse_photos(self):
        d = filedialog.askdirectory(title="เลือกโฟลเดอร์รูปคน (ชื่อไฟล์ = เลขพาสปอร์ต)",
                                    initialdir=self.photos_dir.get() or BASE_DIR)
        if d:
            self.photos_dir.set(d)
            if self.people:
                self.reload()

    def browse_qr(self):
        p = filedialog.askopenfilename(title="เลือกไฟล์ QR Code",
                                       filetypes=[("รูปภาพ", "*.png *.jpg *.jpeg"), ("ทุกไฟล์", "*.*")],
                                       initialdir=os.path.dirname(self.qr_path.get()) or BASE_DIR)
        if p:
            self.qr_path.set(p)

    def reload(self):
        path = self.xlsx_path.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning("ไม่พบไฟล์", "กรุณาเลือกไฟล์ Excel ที่มีอยู่จริง"); return
        try:
            people, warnings = load_people(path)
        except Exception as e:
            messagebox.showerror("อ่านไฟล์ไม่ได้", str(e)); return
        self.people = people
        for item in self.tree.get_children():
            self.tree.delete(item)
        photos_dir = self.photos_dir.get().strip() or None
        missing_photo = 0
        for i, p in enumerate(people, start=1):
            passport = p[config.COL_PASSPORT]
            has_photo = bool(passport) and find_photo_path(passport, BASE_DIR, photos_dir)
            mark = "OK" if has_photo else "X"
            if not has_photo:
                missing_photo += 1
            tag = () if has_photo else ("missing",)
            self.tree.insert("", "end", tags=tag,
                             values=(i, p[config.COL_THAI], p[config.COL_ENGLISH], passport, mark))
        msg = f"โหลดแล้ว {len(people)} คน"
        if missing_photo:
            msg += f"  |  ไม่พบรูป {missing_photo} คน (แถวสีแดง)"
        if warnings:
            msg += f"  |  {len(warnings)} คำเตือน"
        self.status.set(msg)

    def generate(self):
        if not self.people:
            messagebox.showwarning("ไม่มีข้อมูล", "กรุณาโหลดข้อมูลจาก Excel ก่อน"); return
        os.makedirs(os.path.join(BASE_DIR, config.OUTPUT_DIR), exist_ok=True)
        default_name = f"bagtags_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        out = filedialog.asksaveasfilename(title="บันทึก PDF", defaultextension=".pdf",
                                           initialfile=default_name,
                                           initialdir=os.path.join(BASE_DIR, config.OUTPUT_DIR),
                                           filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        photos_dir = self.photos_dir.get().strip() or None
        qr_path = self.qr_path.get().strip() or None
        try:
            n = generate_pdf(self.people, BASE_DIR, out, photos_dir=photos_dir, qr_path=qr_path)
        except Exception as e:
            messagebox.showerror("สร้าง PDF ไม่สำเร็จ", f"{e}\n\n{traceback.format_exc()}"); return
        # จำนวนใบต่อหน้าต่างกันตามโหมด: มี QR = 2xROWS, ไม่มี QR = 2xROWS_NOQR
        _has_qr = bool(qr_path and os.path.exists(qr_path))
        _rows = config.ROWS if _has_qr else getattr(config, "ROWS_NOQR", config.ROWS)
        _per_page = config.COLS * _rows
        pages = (n + _per_page - 1) // _per_page
        self.status.set(f"สร้างเสร็จ: {n} ใบ / {pages} หน้า")
        if messagebox.askyesno("เสร็จแล้ว",
                               f"สร้างใบติดกระเป๋า {n} ใบ ({pages} หน้า)\n\n{out}\n\nเปิดไฟล์เลยไหม?"):
            self._open_file(out)

    def _open_file(self, path):
        try:
            if sys.platform == "darwin":
                os.system(f'open "{path}"')
            elif os.name == "nt":
                os.startfile(path)  # type: ignore
            else:
                os.system(f'xdg-open "{path}"')
        except Exception:
            pass


# =========================================================
#   แท็บ 3: สร้างใบติดพาสปอร์ต → PDF
# =========================================================
class PassportTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.xlsx_path = tk.StringVar(value=self._default_xlsx())
        self.photos_dir = tk.StringVar(value=os.path.join(BASE_DIR, config.PHOTOS_DIR))
        self.grp_leader = tk.StringVar(value="")
        self.grp_name = tk.StringVar(value=getattr(config, "PLABEL_GRP_NAME_DEFAULT", "AL-FAYARD"))
        self.grp_no = tk.StringVar(value="1")
        self.people = []
        self._build()
        if os.path.exists(self.xlsx_path.get()):
            self.reload()

    def _default_xlsx(self):
        p = os.path.join(BASE_DIR, "passengers.xlsx")
        return p if os.path.exists(p) else ""

    def _build(self):
        pad = {"padx": 10, "pady": 5}
        top = ttk.Frame(self); top.pack(fill="x", **pad)
        ttk.Label(top, text="ไฟล์ Excel:", width=11).pack(side="left")
        ttk.Entry(top, textvariable=self.xlsx_path).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="เลือก...", command=self.browse).pack(side="left")
        ttk.Button(top, text="โหลดใหม่", command=self.reload).pack(side="left", padx=4)

        prow = ttk.Frame(self); prow.pack(fill="x", padx=10)
        ttk.Label(prow, text="โฟลเดอร์รูป:", width=11).pack(side="left")
        ttk.Entry(prow, textvariable=self.photos_dir).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(prow, text="เลือก...", command=self.browse_photos).pack(side="left")

        # ---- ช่องที่แก้ได้ก่อนสร้าง (แต่ละรอบไม่เหมือนกัน) ----
        box = ttk.LabelFrame(self, text="ข้อมูลกลุ่ม (แก้ได้ก่อนสร้าง — เหมือนกันทุกใบ)")
        box.pack(fill="x", padx=10, pady=6)
        g1 = ttk.Frame(box); g1.pack(fill="x", padx=8, pady=4)
        ttk.Label(g1, text="Grp.Leader (ผู้นำกลุ่ม):", width=20).pack(side="left")
        ttk.Entry(g1, textvariable=self.grp_leader).pack(side="left", fill="x", expand=True, padx=6)
        g2 = ttk.Frame(box); g2.pack(fill="x", padx=8, pady=4)
        ttk.Label(g2, text="Grp.Name:", width=20).pack(side="left")
        ttk.Entry(g2, textvariable=self.grp_name, width=22).pack(side="left", padx=6)
        ttk.Label(g2, text="Grp.No.:").pack(side="left", padx=(12, 0))
        ttk.Entry(g2, textvariable=self.grp_no, width=8).pack(side="left", padx=6)
        ttk.Label(box, text="No. เรียงตามลำดับรายชื่อใน Excel อัตโนมัติ (1, 2, 3, ...)",
                  foreground="#888").pack(anchor="w", padx=8, pady=(0, 4))

        mid = ttk.Frame(self); mid.pack(fill="both", expand=True, **pad)
        cols = ("no", "name", "passport", "photo")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=10)
        for c, txt, w in [("no", "No.", 45), ("name", "Name (ชื่อบนใบติด)", 290),
                          ("passport", "พาสปอร์ต", 100), ("photo", "รูป", 50)]:
            self.tree.heading(c, text=txt); self.tree.column(c, width=w, anchor="w")
        self.tree.column("no", anchor="center"); self.tree.column("photo", anchor="center")
        vsb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True); vsb.pack(side="right", fill="y")
        self.tree.tag_configure("missing", foreground="#c0392b")

        bottom = ttk.Frame(self); bottom.pack(fill="x", **pad)
        self.status = tk.StringVar(value="ยังไม่ได้โหลดข้อมูล")
        ttk.Label(bottom, textvariable=self.status).pack(side="left")
        ttk.Button(bottom, text="สร้าง PDF (ใบติด + แผ่นรูป)", command=self.generate).pack(side="right")

    def set_excel(self, path):
        """เรียกจากแท็บสแกน: ตั้งไฟล์ Excel ใหม่แล้วโหลดตาราง"""
        self.xlsx_path.set(path)
        self.reload()

    def browse(self):
        p = filedialog.askopenfilename(title="เลือกไฟล์ Excel",
                                       filetypes=[("Excel", "*.xlsx"), ("ทุกไฟล์", "*.*")], initialdir=BASE_DIR)
        if p:
            self.xlsx_path.set(p); self.reload()

    def browse_photos(self):
        d = filedialog.askdirectory(title="เลือกโฟลเดอร์รูปคน (ชื่อไฟล์ = เลขพาสปอร์ต)",
                                    initialdir=self.photos_dir.get() or BASE_DIR)
        if d:
            self.photos_dir.set(d)
            if self.people:
                self.reload()

    def reload(self):
        path = self.xlsx_path.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning("ไม่พบไฟล์", "กรุณาเลือกไฟล์ Excel ที่มีอยู่จริง"); return
        try:
            people, warnings = load_people(path)
        except Exception as e:
            messagebox.showerror("อ่านไฟล์ไม่ได้", str(e)); return
        self.people = people
        for item in self.tree.get_children():
            self.tree.delete(item)
        photos_dir = self.photos_dir.get().strip() or None
        missing_name = 0
        missing_photo = 0
        for i, p in enumerate(people, start=1):
            name = (p.get(config.COL_ENGLISH) or "").strip() or (p.get(config.COL_THAI) or "").strip()
            passport = p.get(config.COL_PASSPORT, "")
            if not name:
                missing_name += 1
            has_photo = bool(passport) and find_photo_path(passport, BASE_DIR, photos_dir)
            if not has_photo:
                missing_photo += 1
            tag = () if (name and has_photo) else ("missing",)
            self.tree.insert("", "end", tags=tag,
                             values=(i, name or "(ไม่มีชื่อ)", passport, "OK" if has_photo else "X"))
        msg = f"โหลดแล้ว {len(people)} คน"
        if missing_name:
            msg += f"  |  ไม่มีชื่อ {missing_name}"
        if missing_photo:
            msg += f"  |  ไม่พบรูป {missing_photo} (แถวสีแดง)"
        self.status.set(msg)

    def generate(self):
        if not self.people:
            messagebox.showwarning("ไม่มีข้อมูล", "กรุณาโหลดข้อมูลจาก Excel ก่อน"); return
        os.makedirs(os.path.join(BASE_DIR, config.OUTPUT_DIR), exist_ok=True)
        default_name = f"passport_labels_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        out = filedialog.asksaveasfilename(title="บันทึก PDF", defaultextension=".pdf",
                                           initialfile=default_name,
                                           initialdir=os.path.join(BASE_DIR, config.OUTPUT_DIR),
                                           filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        photos_dir = self.photos_dir.get().strip() or None
        # ไฟล์แผ่นรูป: ตั้งชื่อคู่กับไฟล์ใบติด (labels -> photos) วางโฟลเดอร์เดียวกัน
        base, ext = os.path.splitext(out)
        if "labels" in os.path.basename(base):
            photo_out = base.replace("labels", "photos") + ext
        else:
            photo_out = base + "_photos" + ext
        try:
            n = generate_passport_labels(
                self.people, BASE_DIR, out,
                grp_leader=self.grp_leader.get().strip(),
                grp_name=self.grp_name.get().strip() or "AL-FAYARD",
                grp_no=self.grp_no.get().strip() or "1")
            n_ph, missing = generate_photo_sheet(
                self.people, BASE_DIR, photo_out, photos_dir=photos_dir)
        except Exception as e:
            messagebox.showerror("สร้าง PDF ไม่สำเร็จ", f"{e}\n\n{traceback.format_exc()}"); return
        per_page = config.PLABEL_COLS * config.PLABEL_ROWS
        pages = (n + per_page - 1) // per_page
        ph_per = config.PSHEET_COLS * config.PSHEET_ROWS
        ph_pages = (n_ph + ph_per - 1) // ph_per
        self.status.set(f"เสร็จ: ใบติด {n} ใบ/{pages} หน้า | แผ่นรูป {n_ph} รูป/{ph_pages} หน้า"
                        + (f" | ไม่พบรูป {missing}" if missing else ""))
        warn = f"\n\n⚠ ไม่พบรูป {missing} คน (ช่องนั้นจะเป็นกรอบ NO PHOTO)" if missing else ""
        if messagebox.askyesno("เสร็จแล้ว",
                               f"สร้าง 2 ไฟล์แล้ว:\n\n"
                               f"1) ใบติดพาสปอร์ต: {n} ใบ ({pages} หน้า)\n   {out}\n\n"
                               f"2) แผ่นรวมรูป: {n_ph} รูป ({ph_pages} หน้า)\n   {photo_out}{warn}\n\n"
                               f"เปิดไฟล์ใบติดเลยไหม?"):
            self._open_file(out)
            self._open_file(photo_out)

    def _open_file(self, path):
        try:
            if sys.platform == "darwin":
                os.system(f'open "{path}"')
            elif os.name == "nt":
                os.startfile(path)  # type: ignore
            else:
                os.system(f'xdg-open "{path}"')
        except Exception:
            pass


# =========================================================
#   หน้าต่างหลัก: รวม 3 แท็บ
# =========================================================
class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Alfayard 1441 — สแกนพาสปอร์ต + ใบติดกระเป๋า + ใบติดพาสปอร์ต")
        self.geometry("720x680")
        self.minsize(620, 580)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        self.tag_tab = TagTab(nb)
        self.passport_tab = PassportTab(nb)
        self.scan_tab = ScanTab(nb, on_excel_ready=self._excel_ready)

        nb.add(self.scan_tab, text="  1) สแกนพาสปอร์ต → Excel  ")
        nb.add(self.tag_tab, text="  2) สร้างใบติดกระเป๋า → PDF  ")
        nb.add(self.passport_tab, text="  3) สร้างใบติดพาสปอร์ต → PDF  ")
        self.nb = nb

    def _excel_ready(self, path):
        """สแกนเสร็จ → ป้อน Excel ให้แท็บใบติดกระเป๋า + ใบติดพาสปอร์ต แล้วสลับไปแท็บใบติดกระเป๋า"""
        try:
            self.tag_tab.set_excel(path)
            try:
                self.passport_tab.set_excel(path)
            except Exception:
                pass
            self.nb.select(self.tag_tab)
        except Exception:
            pass


if __name__ == "__main__":
    MainApp().mainloop()
