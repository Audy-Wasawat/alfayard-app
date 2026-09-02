<div align="center">

# 🧳 Alfayard Passport & Bag Tag Suite

**Scan passports into a spreadsheet, then generate print-ready luggage tags — all in one window.**

A lightweight desktop tool built for travel/Hajj group operators who need to turn a folder of
passport photos into printed bag tags quickly, without paying for cloud OCR.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-lightgrey.svg)]()
[![OCR](https://img.shields.io/badge/OCR-Tesseract%20%2B%20Gemini-green.svg)]()
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](#-license)

</div>

---

## ✨ Overview

This is a single Python/Tkinter application with **two tabs** that cover the whole workflow:

| Tab | What it does | Output |
|-----|--------------|--------|
| **1 · Passport Scanner** | Reads a folder of passport photos and extracts Thai name, English name, and passport number | `passengers.xlsx` |
| **2 · Bag Tag Generator** | Turns that spreadsheet + a folder of ID photos into an A4 PDF of luggage tags (8 per page) | `bagtags_<timestamp>.pdf` |

When a scan finishes, the resulting Excel file is **handed straight to Tab 2 automatically** — no
switching programs, no re-selecting files.

---

## 🚀 Features

- **One window, one launcher.** Double-click `START.bat` (Windows) — dependencies install on first run.
- **Three OCR modes** so you only pay (in quota) for what you need:
  - `Free / Offline` — Tesseract only, no internet.
  - `Free + Gemini fill (recommended)` — Tesseract first; only the fields it fails on are sent to Gemini.
  - `Gemini only` — best accuracy on skewed / glare-heavy scans.
- **Free Gemini tier** — uses Google's free vision API; the key is entered once and remembered locally.
- **Review mode** — rows that couldn't be fully read are highlighted yellow in the spreadsheet.
- **Embedded Thai font (Sarabun)** so PDFs render Thai names correctly on any machine.
- **Auto-fit typography** — long names shrink from 16pt down to fit one line.
- **Photo matching by passport number** — name a photo `AA1234567.jpg` and it's matched automatically.
- **Everything configurable in one file** (`src/config.py`) — tag size, margins, fonts, layout.

---

## 📦 Requirements

- **Python 3.8+** (Anaconda works well)
- Python packages (installed automatically by `START.bat`):
  `reportlab`, `Pillow`, `openpyxl`, `pytesseract`, `google-generativeai`
- **[Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)** with the Thai language pack (`tha`) — required for the free/offline mode
- A **Google Gemini API key** (free) — only for the `auto` and `gemini` modes → get one at <https://aistudio.google.com>

---

## ⚡ Quick Start

### Windows
```bat
:: Just double-click:
START.bat
```
On first launch it installs the required libraries and opens the app.

### macOS / Linux (or manual run)
```bash
pip install -r requirements.txt
python app.py
```

> **Tesseract path:** the app auto-detects Tesseract. If it can't find it, set an environment
> variable `TESSERACT_CMD` to the full path of the executable
> (e.g. `C:\Program Files\Tesseract-OCR\tesseract.exe`).

---

## 📖 Usage

### Tab 1 — Passport Scanner
1. Choose the folder containing passport photos.
2. Pick a mode (`Free`, `Free + Gemini`, or `Gemini only`).
3. For Gemini modes, paste your **Gemini API key** (entered once, remembered afterwards).
4. Click **Scan** → produces `passengers.xlsx`. Incomplete rows are highlighted for review.
5. The spreadsheet is passed to Tab 2 automatically.

### Tab 2 — Bag Tag Generator
1. Excel file (auto-filled from Tab 1, or pick your own).
2. Photo folder — each person's photo named after their passport number, e.g. `AA1234567.jpg`.
3. QR image (optional, per event).
4. Click **Generate PDF** → saved to `output/`.

---

## 🔑 Getting a Free Gemini API Key
1. Go to <https://aistudio.google.com> and sign in with a Google account.
2. Click **Get API key → Create API key**.
3. Copy the key and paste it into the app (no credit card required).

---

## 🖼️ Photo Naming Convention
Photos are matched to people by **passport number as the filename**:

```
photos/
├── AA1234567.jpg
├── BB7654321.png
└── CC1112223.jpeg
```
Supported extensions: `.jpg .jpeg .png` (any case).

---

## 🛠️ Configuration
All layout constants live in **`src/config.py`** (measurements in millimetres):

| Setting | Default | Meaning |
|---------|---------|---------|
| `TAG_W_MM` / `TAG_H_MM` | 90 × 63 | Tag size (9 × 6.3 cm) |
| `COLS` / `ROWS` | 2 × 4 | Tags per page (8) |
| `PHOTO_W_MM` / `PHOTO_H_MM` | 24 × 32 | Photo box (3:4 ratio) |
| `QR_SIZE_MM` | 21 | QR code size |
| `NAME_START_PT` / `NAME_MIN_PT` | 16 / 8 | Auto-shrink name font range |
| `COMPANY_NAME` | Alfayard 1441 Co., Ltd. | Printed on every tag |

---

## 📁 Project Structure
```
alfayard-app/
├── START.bat            # Windows launcher (installs deps + runs app)
├── app.py               # Unified 2-tab GUI
├── requirements.txt
├── passengers.xlsx      # Example data
├── gemini_api_key.txt   # Saved API key (git-ignored)
├── assets/qr_code.png   # Default QR
├── fonts/Sarabun-*.ttf  # Embedded Thai font
├── photos/              # ID photos (filename = passport no.)
├── output/              # Generated PDFs
└── src/
    ├── config.py            # All layout settings
    ├── passport_scanner.py  # OCR: Tesseract + MRZ + Gemini
    ├── excel_export.py      # Scan results → xlsx
    ├── excel_loader.py      # xlsx → people
    ├── photo.py             # Center-crop to 3:4
    └── generator.py         # Draw the PDF
```

---

## 🔍 How OCR Works
- **Passport number** — regex `[A-Z]{1,2}\d{7}` from the data page, falling back to the MRZ.
- **English name** — title + given name from the data page, surname from the `Surname` field (cleaner than the MRZ).
- **Thai name** — full-page Thai OCR, matching the honorific line (นาย / นาง / นางสาว / เด็กชาย / เด็กหญิง).
- **Gemini fallback** — in `auto` mode, only fields Tesseract couldn't read are sent to Gemini, saving quota while fixing skewed or glare-heavy scans.

> 💡 **Tip:** Flat, well-lit scans read almost perfectly. Angled phone photos are where the Gemini
> fallback earns its keep.

---

## 🖨️ Printing
When printing the PDF, set the scale to **"Actual size / 100%"** — do **not** use *Fit to page*,
or the tag dimensions will be wrong.

---

## 🐙 Publishing to GitHub (first-time setup)

> These are one-time developer steps. Regular users only need `START.bat`.

**Requirements to publish:** [Git](https://git-scm.com/download/win) installed and a free
[GitHub](https://github.com) account.

1. Create a new **empty** repository on GitHub (do **not** add a README, .gitignore, or license —
   this project already has them).
2. Open a terminal (Git Bash) in this folder and run:

```bash
git init
git add .
git commit -m "Initial commit: passport scanner + bag tag generator"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

The `.gitignore` automatically keeps these **out** of the repository:

- `gemini_api_key.txt` — your private API key
- real ID photos in `photos/` (`*.jpg`, `*.png`, …)
- generated PDFs, `__pycache__/`, and other build artifacts

So your API key and personal data are never uploaded.

---

## 📄 License
Released under the **MIT License** — free to use, modify, and distribute.

---

<div align="center">
Made for <b>Alfayard 1441 Co., Ltd.</b> · Hajj & Umrah operations
</div>
