# -*- coding: utf-8 -*-
"""
SpendSnap AI - Integration Test Suite
Covers the full Month 1 pipeline: upload → OCR → parse → DB → CRUD.
Run with:  .\\venv\\Scripts\\python test_pipeline.py
"""
import sys
import os
import requests
from io import BytesIO
from PIL import Image


BASE_URL = os.environ.get("SPENDSNAP_URL", "http://127.0.0.1:8000")
PASS = "[PASS]"
FAIL = "[FAIL]"


def generate_test_image(label: str = "default") -> bytes:
    """Generate a tiny white PNG. The filename triggers mock OCR templates."""
    img = Image.new("RGB", (100, 100), color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def step(n: int, description: str):
    print(f"\n{n}. {description}")


def check(condition: bool, label: str):
    icon = PASS if condition else FAIL
    print(f"   {icon}  {label}")
    if not condition:
        sys.exit(1)


def run_test():
    print("=" * 55)
    print(f"  SpendSnap AI - Integration Test Pipeline")
    print("=" * 55)

    # ── 1. Health check ──────────────────────────────────────
    step(1, "API health check")
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=5)
        r.raise_for_status()
        health = r.json()
    except Exception as e:
        print(f"   {FAIL}  Cannot reach backend at {BASE_URL}: {e}")
        print("   Make sure the server is running (Run_SpendSnap_Dashboard.bat or uvicorn).")
        sys.exit(1)

    check(health.get("status") == "healthy", f"status=healthy")
    check("mock_ocr" in health, "mock_ocr field present")
    check("max_upload_mb" in health, "max_upload_mb field present")
    print(f"   [INFO] mock_ocr={health['mock_ocr']}, db={health['database_type']}, max={health['max_upload_mb']} MB")

    # ── 2. File size rejection ───────────────────────────────
    step(2, "Upload rejection — oversized file")
    max_mb = health["max_upload_mb"]
    oversized = b"0" * (max_mb * 1024 * 1024 + 1)
    r = requests.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("big.png", oversized, "image/png")},
        timeout=15,
    )
    check(r.status_code == 413, f"HTTP 413 returned for {max_mb} MB+ file (got {r.status_code})")

    # ── 3. Unsupported type rejection ────────────────────────
    step(3, "Upload rejection — unsupported file type")
    r = requests.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("doc.docx", b"fake", "application/vnd.openxmlformats")},
        timeout=10,
    )
    check(r.status_code == 415, f"HTTP 415 returned for .docx (got {r.status_code})")

    # ── 4. Successful Swiggy upload ──────────────────────────
    step(4, "Swiggy receipt upload — OCR + parse")
    img_data = generate_test_image("swiggy")
    r = requests.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("swiggy_test_receipt.png", img_data, "image/png")},
        timeout=30,
    )
    check(r.status_code == 201, f"HTTP 201 (got {r.status_code}): {r.text[:120]}")

    result = r.json()
    expense = result["expense"]
    receipt = result["receipt"]

    check("id" in expense, "expense.id present")
    check("merchant" in expense and expense["merchant"] != "", "merchant extracted")
    check("amount" in expense and expense["amount"] > 0, f"amount > 0 (got {expense['amount']})")
    check("source_type" in expense, "source_type field present")
    check(expense["source_type"] == "photo", f"source_type='photo' (got {expense['source_type']})")
    check("transaction_date" in expense, "transaction_date field present")
    check("raw_text" in receipt and len(receipt["raw_text"]) > 0, "raw_text populated")

    print(f"   [INFO] merchant={expense['merchant']!r}, amount=Rs.{expense['amount']}, "
          f"date={expense['transaction_date']}, source={expense['source_type']}")

    expense_id = expense["id"]

    # ── 5. Screenshot source_type detection ─────────────────
    step(5, "Screenshot source_type — filename heuristic")
    r = requests.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("phonepe_screenshot_receipt.png", img_data, "image/png")},
        timeout=30,
    )
    check(r.status_code == 201, f"HTTP 201 (got {r.status_code})")
    ss_expense = r.json()["expense"]
    check(ss_expense["source_type"] == "screenshot",
          f"source_type='screenshot' (got {ss_expense['source_type']})")
    screenshot_id = ss_expense["id"]

    # ── 6. List expenses ─────────────────────────────────────
    step(6, "List all expenses")
    r = requests.get(f"{BASE_URL}/api/expenses", timeout=10)
    r.raise_for_status()
    expenses = r.json()
    check(len(expenses) >= 2, f"At least 2 expenses in DB (found {len(expenses)})")

    ids_in_response = [e["id"] for e in expenses]
    check(expense_id in ids_in_response, f"Swiggy expense (id={expense_id}) in list")

    # ── 7. Update expense ────────────────────────────────────
    step(7, f"Correct expense #{expense_id}")
    payload = {
        "merchant": "Swiggy (Bundl Technologies)",
        "amount": 350.00,
        "category": "Food & Dining",
        "source_type": "screenshot",
    }
    r = requests.put(f"{BASE_URL}/api/expenses/{expense_id}", json=payload, timeout=10)
    r.raise_for_status()
    updated = r.json()

    check(updated["merchant"] == "Swiggy (Bundl Technologies)", "merchant updated")
    check(updated["amount"] == 350.00, "amount updated")
    check(updated["category"] == "Food & Dining", "category updated")
    check(updated["source_type"] == "screenshot", "source_type updated")

    # ── 8. Delete expense ────────────────────────────────────
    step(8, f"Delete screenshot expense #{screenshot_id}")
    r = requests.delete(f"{BASE_URL}/api/expenses/{screenshot_id}", timeout=10)
    check(r.status_code == 204, f"HTTP 204 (got {r.status_code})")

    # Verify it's gone
    r = requests.get(f"{BASE_URL}/api/expenses", timeout=10)
    remaining_ids = [e["id"] for e in r.json()]
    check(screenshot_id not in remaining_ids, f"Expense #{screenshot_id} removed from list")

    print("\n" + "=" * 55)
    print(f"  {PASS} All integration tests passed!")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    run_test()
