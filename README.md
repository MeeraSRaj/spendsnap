# SpendSnap AI - Your Financial Memory

This is the codebase for **SpendSnap AI (Your Financial Memory)**.

## Month 1 Scope: Dumb but Working
- End-to-end pipeline: **Image Selection → OCR Parsing → Extracted Details → Database Persistence**.
- **Browser Dashboard UI**: Served directly from the backend to verify and test locally without emulator setup.
- **Mobile Expo App**: Camera receipt scanning, verification, and history card list.

---

## How to Run & Test (No CLI Needed!)

On Windows, simply double-click the launcher script in the root directory:
```bash
Run_SpendSnap_Dashboard.bat
```
This automatically:
1. Starts the backend server in a minimized background shell.
2. Launches your default web browser to the dashboard: `http://127.0.0.1:8000/`.
3. Keeps a control window open. Pressing any key in the control window will shut down the server.

*To test the OCR pipeline, drag-and-drop a receipt screenshot (or search for images named `swiggy`, `starbucks`, or `fuel` to trigger specific realistic mock receipt layouts).*

---

## Advanced CLI Commands

### 1. Start the FastAPI Backend Manually
```bash
cd backend
.\venv\Scripts\activate
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
*Note: If you have Google Cloud Vision credentials, create a `.env` file in the `backend/` directory and set `GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json`. Otherwise, the system automatically uses **Mock OCR Mode**.*

### 2. Start the Expo Mobile Client
```bash
cd mobile
npm run start
```
*Press `a` for Android Emulator, `i` for iOS Simulator, or scan the Metro QR code using the **Expo Go** app on your physical phone.*

### 3. Run Integration Tests
```bash
cd backend
.\venv\Scripts\python test_pipeline.py
```

---

## Project Structure
```
spendsnap/
├── Run_SpendSnap_Dashboard.bat  # Double-clickable Windows launcher
├── backend/
│   ├── config.py         # App configurations (handles SQLite and OCR fallbacks)
│   ├── database.py       # SQL session management
│   ├── index.html        # Local web dashboard UI (served at http://127.0.0.1:8000/)
│   ├── main.py           # FastAPI app routers (upload, list, update, delete)
│   ├── models.py         # Receipt and Expense database tables
│   ├── ocr.py            # OCR client (Google Cloud Vision & Regex Parser)
│   ├── requirements.txt  # Python packages
│   └── test_pipeline.py  # Automated integration test pipeline
└── mobile/
    ├── App.tsx           # React Native UI (Dark-mode feed, camera upload, correction modal)
    └── package.json      # NPM dependencies (Expo SDK 56)
```
