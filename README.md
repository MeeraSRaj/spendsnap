<div align="center">

# 📸 SpendSnap AI
### *Your Financial Memory*

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React Native](https://img.shields.io/badge/React_Native-Expo_SDK_56-61DAFB?style=flat-square&logo=react&logoColor=black)](https://expo.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](./mobile/LICENSE)

**Stop losing receipts. Start understanding your money.**  
SpendSnap turns any receipt photo, UPI screenshot, or bank PDF into a searchable, categorized expense record — automatically.

</div>

---

## ✨ What It Does

| Input | → | Output |
|---|---|---|
| 📷 Receipt photo | OCR + regex parsing | `{ merchant, amount, date, category, source_type }` |
| 🖼️ UPI/bank screenshot | Filename heuristic + OCR | Labelled `source_type: "screenshot"` |
| 📄 PDF bank statement | pdfplumber → Vision fallback | Full transaction history |
| 💬 Bank SMS text | Regex + normalisation | `{ merchant, amount, date, category, source_type: "sms" }` |

> **Current Phase:** Month 1 core pipeline — input → OCR/PDF extraction → parsed JSON → database.

---

## 🏗️ Architecture

```
spendsnap/
├── Run_SpendSnap_Dashboard.bat       # One-click Windows launcher
│
├── backend/                          # Python · FastAPI
│   ├── main.py                       # API routes: upload, list, update, delete
│   ├── ocr.py                        # Vision API + Mock OCR + PDF extraction + date parser
│   ├── models.py                     # Receipt & Expense ORM (SQLAlchemy)
│   ├── schemas.py                    # Pydantic request/response schemas
│   ├── database.py                   # Session management (SQLite → Postgres-ready)
│   ├── config.py                     # pydantic-settings + .env
│   ├── index.html                    # Browser dashboard (served at /)
│   ├── test_pipeline.py              # Integration test suite
│   ├── requirements.txt
│   ├── sms_parsers/                  # Bank SMS normalisation (HDFC, ICICI, SBI, Paytm)
│   └── data/
│       └── merchants.json            # Indian merchant → category lookup (Phase 3)
│
└── mobile/                           # TypeScript · React Native · Expo SDK 56
    ├── App.tsx                       # Camera upload, dark-mode feed, edit modal
    ├── index.ts                      # Expo entry point
    ├── app.json                      # Expo app config
    └── package.json
```

**Data flow:**
```
[Camera / Gallery / PDF]
        │
        ▼
POST /api/upload
        │
   ┌────┴────────────────────────────┐
   │ Image?            PDF?          │
   │  Google Vision    pdfplumber    │
   │  (mock fallback)  (Vision fallback for scanned)
   └────┬────────────────────────────┘
        │ raw_text
        ▼
  Regex Parser
  merchant · amount · transaction_date (OCR-extracted)
        │
        ▼
  SQLite / Postgres
  Receipt + Expense rows
  (source_type · user_id stub · ai fields ready)
```

---

## 🚀 Quick Start

### Option A — Windows One-Click (No CLI needed)

```
Double-click:  Run_SpendSnap_Dashboard.bat
```

This will:
1. Start the FastAPI backend in a minimised background window
2. Open `http://127.0.0.1:8000` in your default browser
3. Keep a control window open — **press any key to stop the server**

> 💡 **Test without real receipts:** Upload any image named `swiggy`, `starbucks`, `fuel`, `amazon`, or `canteen` to trigger realistic mock receipt templates. Name it `phonepe_screenshot_...` to test screenshot source detection.

---

### Option B — Manual CLI

#### 1. Backend

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate          # Windows
# source venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Interactive API docs: `http://127.0.0.1:8000/docs`

#### 2. Mobile (Expo)

```bash
cd mobile
npm install
npm run start
```

| Key | Action |
|-----|--------|
| `a` | Open Android emulator |
| `i` | Open iOS simulator |
| Scan QR | Open in **Expo Go** on physical device |

#### 3. Integration Tests

```bash
cd backend
.\venv\Scripts\python test_pipeline.py
```

Tests covered:
- ✅ Health check (OCR mode, DB type, upload limit)
- ✅ Oversized file rejection (HTTP 413)
- ✅ Unsupported file type rejection (HTTP 415)
- ✅ Swiggy receipt upload — merchant, amount, `transaction_date`, `source_type`
- ✅ Screenshot `source_type` detection from filename
- ✅ Expense list ordering
- ✅ Expense update (including `source_type` and `category`)
- ✅ Expense delete + verify removal

---

## ⚙️ Configuration

Create `backend/.env` to override any default:

```env
# ── Database ─────────────────────────────────────────────────
# Default: local SQLite. Switch to Postgres for production.
DATABASE_URL=postgresql://user:password@localhost:5432/spendsnap

# ── OCR ──────────────────────────────────────────────────────
# Omit to use Mock OCR (no credentials needed for local dev).
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# ── Uploads ──────────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB=10

# ── CORS ─────────────────────────────────────────────────────
# Add your production domain when deploying.
# Default allows localhost:8081 (Expo) and localhost:3000.
CORS_ORIGINS=["https://app.yourdomain.com","http://localhost:8081"]
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Browser dashboard UI |
| `GET` | `/api/health` | Server status, OCR mode, upload limit |
| `POST` | `/api/upload` | Upload image or PDF → returns parsed expense |
| `POST` | `/api/expenses/sms` | Parse bank SMS text → returns parsed expense |
| `GET` | `/api/expenses` | All expenses, ordered by receipt date |
| `PUT` | `/api/expenses/{id}` | Correct any field (merchant, amount, category, source_type) |
| `DELETE` | `/api/expenses/{id}` | Remove expense + deletes image file from disk |

**Upload response shape:**
```json
{
  "receipt": {
    "id": 1,
    "file_path": "backend/uploads/uuid.png",
    "raw_text": "Swiggy Delivery Receipt\n...",
    "created_at": "2026-06-20T13:42:00Z"
  },
  "expense": {
    "id": 1,
    "merchant": "Bundl Technologies Private Ltd",
    "amount": 349.0,
    "category": "Uncategorized",
    "transaction_date": "2026-06-20T13:42:00",
    "source_type": "photo",
    "ai_suggested_category": null,
    "category_confidence": null,
    "user_id": null,
    "created_at": "2026-06-21T10:00:00Z"
  }
}
```

**Accepted file types:** `.jpg`, `.jpeg`, `.png`, `.webp`, `.pdf`  
**Max upload size:** 10 MB (configurable via `MAX_UPLOAD_SIZE_MB`)

---

## 🗄️ Data Model

### `Expense` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Primary key |
| `receipt_id` | int FK | Linked receipt row |
| `merchant` | string | Extracted from first OCR line |
| `amount` | float | Largest/labelled total on receipt |
| `transaction_date` | datetime? | Date extracted from OCR text (not upload time) |
| `category` | string | `"Uncategorized"` until Phase 3 |
| `source_type` | string | `photo \| screenshot \| pdf \| sms` |
| `ai_suggested_category` | string? | Populated by Claude in Phase 3 |
| `category_confidence` | float? | AI confidence score (0.0–1.0) |
| `user_id` | string? | Auth stub — wired up in Phase 2 |
| `created_at` | datetime | Upload timestamp |

---

## 🗺️ Roadmap

| Phase | Weeks | Status | Milestone |
|-------|-------|--------|-----------|
| **1 — Core Pipeline** | 1–3 | ✅ Done | Image/PDF → OCR → DB with full audit fields |
| **2 — Mobile Shell** | 3–5 | 🔄 In progress | Camera picker, upload UX, user auth |
| **3 — Smart Features** | 5–10 | 📋 Planned | Claude AI categorisation, subscription detection, weekly summaries |
| **4 — Warranty Vault** | 10–14 | 📋 Planned | Product parsing, warranty tracking, push notifications |

**Next up (Phase 2):**
- [ ] Upload progress bar + offline queue for slow connections
- [ ] Auth via Supabase — wire `user_id` to expense rows
- [ ] Supabase Storage for receipt images (replace local `file_path`)
- [x] Bank SMS normalisation layer (`sms_parsers/hdfc.py`, `sms_parsers/icici.py`, …)

---

## 🛠️ Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| **Mobile** | React Native + Expo SDK 56 | Single codebase, camera + file picker, TypeScript |
| **Backend** | FastAPI (Python) | Python-native OCR/AI libs, async I/O |
| **OCR** | Google Cloud Vision | Best Hindi/regional text and messy fonts |
| **PDF** | pdfplumber + PyMuPDF | Machine-readable first; renders scanned pages as fallback |
| **Database** | SQLite → Postgres-ready | Zero-config dev, production-grade swap |
| **ORM** | SQLAlchemy 2.0 | Type-safe queries |
| **Validation** | Pydantic v2 | Schema enforcement, `.env` settings |

---

## 🤝 Contributing

1. Fork → branch off `main`
2. Follow the **phase order** — don't build Phase 3 features before Phase 2 is solid
3. Test with at least 5 real receipt images before opening a PR
4. When you encounter a new Indian merchant name, add it to `backend/data/merchants.json`

---

## 📄 License

[MIT](./mobile/LICENSE) · Built with ☕ and too many Indian restaurant bills.
