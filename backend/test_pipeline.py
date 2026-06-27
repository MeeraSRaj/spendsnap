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
        headers={"X-User-Id": "test_user"},
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
        headers={"X-User-Id": "test_user"},
        timeout=30,
    )
    check(r.status_code == 201, f"HTTP 201 (got {r.status_code})")
    ss_expense = r.json()["expense"]
    check(ss_expense["source_type"] == "screenshot",
          f"source_type='screenshot' (got {ss_expense['source_type']})")
    screenshot_id = ss_expense["id"]

    # ── 6. List expenses ─────────────────────────────────────
    step(6, "List all expenses")
    r = requests.get(f"{BASE_URL}/api/expenses", headers={"X-User-Id": "test_user"}, timeout=10)
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
    r = requests.put(f"{BASE_URL}/api/expenses/{expense_id}", json=payload, headers={"X-User-Id": "test_user"}, timeout=10)
    r.raise_for_status()
    updated = r.json()

    check(updated["merchant"] == "Swiggy (Bundl Technologies)", "merchant updated")
    check(updated["amount"] == 350.00, "amount updated")
    check(updated["category"] == "Food & Dining", "category updated")
    check(updated["source_type"] == "screenshot", "source_type updated")

    # ── 8. Delete expense ────────────────────────────────────
    step(8, f"Delete screenshot expense #{screenshot_id}")
    r = requests.delete(f"{BASE_URL}/api/expenses/{screenshot_id}", headers={"X-User-Id": "test_user"}, timeout=10)
    check(r.status_code == 204, f"HTTP 204 (got {r.status_code})")

    # Verify it's gone
    r = requests.get(f"{BASE_URL}/api/expenses", headers={"X-User-Id": "test_user"}, timeout=10)
    remaining_ids = [e["id"] for e in r.json()]
    check(screenshot_id not in remaining_ids, f"Expense #{screenshot_id} removed from list")

    # ── 9. User Isolation ────────────────────────────────────
    step(9, "User Isolation — check cross-user privacy")
    
    # User A uploads an expense
    headers_a = {"X-User-Id": "user_a"}
    headers_b = {"X-User-Id": "user_b"}
    
    img_data = generate_test_image("swiggy")
    r = requests.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("swiggy_user_a.png", img_data, "image/png")},
        headers=headers_a,
        timeout=15
    )
    check(r.status_code == 201, "User A upload succeeded")
    expense_a = r.json()["expense"]
    expense_a_id = expense_a["id"]
    
    # User B lists expenses - should NOT see User A's expense
    r = requests.get(f"{BASE_URL}/api/expenses", headers=headers_b, timeout=10)
    expenses_b = r.json()
    b_ids = [e["id"] for e in expenses_b]
    check(expense_a_id not in b_ids, "User B cannot view User A's expense")
    
    # User B tries to delete User A's expense - should return 403 Forbidden
    r = requests.delete(f"{BASE_URL}/api/expenses/{expense_a_id}", headers=headers_b, timeout=10)
    check(r.status_code == 403, f"User B delete of User A's expense rejected with HTTP 403 (got {r.status_code})")
    
    # Clean up User A's expense
    r = requests.delete(f"{BASE_URL}/api/expenses/{expense_a_id}", headers=headers_a, timeout=10)
    check(r.status_code == 204, "User A cleaned up their expense")

    # ── 10. SMS Copy-Paste Normalisation ─────────────────────
    step(10, "SMS Copy-Paste parsing engine")
    
    sms_test_cases = [
        {
            "sms": "Alert: Rs 1,450.00 spent on HDFC Bank Card... at ZOMATO on 20-06-2026.",
            "merchant": "ZOMATO",
            "amount": 1450.00
        },
        {
            "sms": "Dear Customer, txn of INR 320.00 on ICICI Bank Card ...8920 at STARBUCKS on 20-Jun-2026",
            "merchant": "STARBUCKS",
            "amount": 320.00
        },
        {
            "sms": "Txn of Rs 500.00 on SBI Debit Card ...1234 at INDIANOIL on 20-06-2026",
            "merchant": "INDIANOIL",
            "amount": 500.00
        },
        {
            "sms": "Paid Rs. 350.00 to SWIGGY. Wallet Bal: Rs 120. TxnId: 102938",
            "merchant": "SWIGGY",
            "amount": 350.00
        }
    ]
    
    for i, tc in enumerate(sms_test_cases, 1):
        r = requests.post(
            f"{BASE_URL}/api/expenses/sms",
            json={"sms_text": tc["sms"]},
            headers={"X-User-Id": "sms_test_user"},
            timeout=10
        )
        check(r.status_code == 201, f"SMS test case {i} created successfully")
        exp = r.json()
        check(exp["amount"] == tc["amount"], f"Case {i} amount match: expected {tc['amount']}, got {exp['amount']}")
        check(exp["merchant"].upper() == tc["merchant"].upper(), f"Case {i} merchant match: expected {tc['merchant']}, got {exp['merchant']}")
        check(exp["source_type"] == "sms", f"Case {i} source_type='sms'")
        
        # Clean up
        requests.delete(f"{BASE_URL}/api/expenses/{exp['id']}", headers={"X-User-Id": "sms_test_user"}, timeout=10)

    # ── 11. SMS Screenshot OCR normalisation ──────────────────
    step(11, "SMS Screenshot OCR automatic detection")
    img_data = generate_test_image("sms")  # Name contains 'sms' to trigger HDFC SMS template
    r = requests.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("screenshot_sms.png", img_data, "image/png")},
        headers={"X-User-Id": "sms_screenshot_user"},
        timeout=20
    )
    check(r.status_code == 201, "SMS screenshot upload processed successfully")
    sms_exp = r.json()["expense"]
    check(sms_exp["source_type"] == "sms", f"Expected source_type='sms' from screenshot, got {sms_exp['source_type']}")
    check(sms_exp["merchant"].upper() == "STARBUCKS", f"Expected merchant='STARBUCKS', got {sms_exp['merchant']}")
    check(sms_exp["amount"] == 450.00, f"Expected amount=450.00, got {sms_exp['amount']}")
    
    # Clean up
    requests.delete(f"{BASE_URL}/api/expenses/{sms_exp['id']}", headers={"X-User-Id": "sms_screenshot_user"}, timeout=10)

    print("\n" + "=" * 55)
    print(f"  {PASS} All integration tests passed!")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    run_test()
