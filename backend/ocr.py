import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from backend.config import settings

logger = logging.getLogger("spendsnap.ocr")


# ──────────────────────────────────────────────────────────────
# OCR — Google Cloud Vision + Mock fallback
# ──────────────────────────────────────────────────────────────

def perform_ocr(image_bytes: bytes, filename: Optional[str] = None) -> str:
    """
    Performs OCR on the provided image bytes.
    If Google Cloud Vision credentials are set, it queries Google Cloud Vision.
    Otherwise, it falls back to a smart mock OCR generator for testing.
    """
    if not settings.use_mock_ocr:
        try:
            from google.cloud import vision  # lazy import — not required in mock mode
            logger.info("Using Google Cloud Vision API for OCR...")
            client = vision.ImageAnnotatorClient()
            image = vision.Image(content=image_bytes)
            response = client.text_detection(image=image)

            if response.error.message:
                raise Exception(f"Google Cloud Vision API Error: {response.error.message}")

            texts = response.text_annotations
            if texts:
                return texts[0].description
            return ""
        except Exception as e:
            logger.error(f"Failed to run Google Cloud Vision OCR: {e}. Falling back to Mock OCR.")
            # Fall through to mock OCR if API call fails

    # ── Mock OCR generator ──────────────────────────────────────
    logger.info("Using Mock OCR engine...")
    fn = (filename or "").lower()

    if "swiggy" in fn or "food" in fn:
        return (
            "Bundl Technologies Private Ltd\n"
            "Swiggy Delivery Receipt\n"
            "Order ID: #4059283749\n"
            "Date: 20-06-2026 13:42:00\n"
            "-----------------------------\n"
            "1x Paneer Butter Masala   280.00\n"
            "2x Butter Roti            60.00\n"
            "Delivery Partner Fee      35.00\n"
            "Discount (WELCOME50)     -50.00\n"
            "GST & Taxes               24.00\n"
            "-----------------------------\n"
            "Grand Total: INR 349.00\n"
            "Paid via UPI (PhonePe)\n"
            "Thank you for ordering!"
        )
    elif "starbucks" in fn or "coffee" in fn:
        return (
            "Tata Starbucks Private Limited\n"
            "Store #5821 - Indiranagar, Bangalore\n"
            "Date: 18-06-2026 16:15:30\n"
            "Invoice No: INV-882310\n"
            "-----------------------------\n"
            "1x Java Chip Frappuccino   320.00\n"
            "1x Blueberry Muffin        180.00\n"
            "Subtotal                  500.00\n"
            "CGST 2.5%                  12.50\n"
            "SGST 2.5%                  12.50\n"
            "-----------------------------\n"
            "TOTAL: Rs 525.00\n"
            "Paid via Starbucks Card\n"
            "Visit starbucks.in for feedback"
        )
    elif "amazon" in fn or "order" in fn:
        return (
            "Amazon Seller Services Private Limited\n"
            "Tax Invoice / Bill of Supply\n"
            "Order Date: 15-06-2026\n"
            "Invoice Number: IN-99238\n"
            "-----------------------------\n"
            "Product: Amazon Basics HDMI Cable 6ft\n"
            "Unit Price: 399.00\n"
            "Qty: 2\n"
            "Shipping Charge: 40.00\n"
            "Promotion Applied: -40.00\n"
            "Tax (GST 18%): 143.64\n"
            "-----------------------------\n"
            "Total Amount: INR 798.00\n"
            "Payment Method: Amazon Pay ICICI Credit Card"
        )
    elif "fuel" in fn or "petrol" in fn or "indianoil" in fn:
        return (
            "INDIAN OIL CORPORATION LTD\n"
            "COCO BEGUMPET, HYDERABAD\n"
            "Receipt No: 4892 - Pump: 04\n"
            "Date: 19-06-2026 09:12:11\n"
            "-----------------------------\n"
            "Fuel Type: XP95 Petrol\n"
            "Rate/Litre: Rs 109.41\n"
            "Volume (Ltrs): 18.28\n"
            "-----------------------------\n"
            "Amount Received: Rs 2000.00\n"
            "Paid via Cash\n"
            "Save fuel, save environment!"
        )
    elif "canteen" in fn or "college" in fn:
        return (
            "CAMPUS FOODS & CANTEEN\n"
            "REJUVENATION HUB BLOCK A\n"
            "Token No: 82\n"
            "Date: 20-06-2026\n"
            "-----------------------------\n"
            "2x Samosa                  30.00\n"
            "1x Lemon Tea               15.00\n"
            "-----------------------------\n"
            "Total: Rs 45.00\n"
            "Paid via GPay (UPI)"
        )
    elif "sms" in fn:
        return (
            "Alert: Rs 450.00 spent on HDFC Bank Card... at STARBUCKS on 20-06-2026."
        )
    else:
        return (
            "A2B VEG RESTAURANT\n"
            "Adyar Ananda Bhavan - Bangalore\n"
            "Bill No: A2B-2026-99382\n"
            "Date: 20-06-2026 20:30:15\n"
            "-----------------------------\n"
            "2x Special Masala Dosa    180.00\n"
            "1x Filter Coffee           45.00\n"
            "Subtotal                  225.00\n"
            "SGST 2.5%                   5.63\n"
            "CGST 2.5%                   5.63\n"
            "-----------------------------\n"
            "Total Due: Rs 236.26\n"
            "Payment: UPI/NetBanking\n"
            "Thank you! Visit again."
        )


# ──────────────────────────────────────────────────────────────
# PDF text extraction (pdfplumber → Vision API fallback)
# ──────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_bytes: bytes, filename: Optional[str] = None) -> str:
    """
    Extracts text from a PDF using pdfplumber (machine-readable PDFs).
    If pdfplumber returns no text (scanned PDF), falls back to Google Vision
    on the rendered first-page image.
    """
    try:
        import pdfplumber
        from io import BytesIO

        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            pages_text = [page.extract_text() or "" for page in pdf.pages]
        extracted = "\n".join(pages_text).strip()

        if extracted:
            logger.info(f"pdfplumber extracted {len(extracted)} chars from PDF.")
            return extracted

        logger.warning("pdfplumber returned no text — PDF may be scanned. Falling back to Vision API on page image.")
    except ImportError:
        logger.warning("pdfplumber not installed. Install it with: pip install pdfplumber>=0.11.0")
    except Exception as e:
        logger.error(f"pdfplumber failed: {e}")

    # Fallback: render first page as image and run OCR
    try:
        import fitz  # PyMuPDF
        from io import BytesIO

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        logger.info("Rendered PDF page to image — running OCR via Vision API.")
        return perform_ocr(img_bytes, filename=filename)
    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed. Cannot render scanned PDF pages.")
    except Exception as e:
        logger.error(f"PDF page rendering failed: {e}")

    return ""


# ──────────────────────────────────────────────────────────────
# Receipt text parser
# ──────────────────────────────────────────────────────────────

# Date patterns used across Indian receipts and bank statements
_DATE_PATTERNS = [
    # "Date: 20-06-2026" / "Date: 20/06/2026"
    r'(?:date|dated?)[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
    # "Order Date: 15-06-2026"
    r'(?:order|transaction|txn|invoice)[:\s]+date[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
    # Standalone DD-MM-YYYY or DD/MM/YYYY at word boundary
    r'\b(\d{2}[-/]\d{2}[-/]\d{4})\b',
    # YYYY-MM-DD (ISO)
    r'\b(\d{4}[-/]\d{2}[-/]\d{2})\b',
]

# Formats tried when parsing extracted date strings
_DATE_FORMATS = [
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
]


def _parse_date_string(raw: str) -> Optional[datetime]:
    """Try multiple formats to parse a raw date string into a datetime object."""
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def parse_receipt_text(text: str) -> Dict[str, Any]:
    """
    Parses raw OCR text from a receipt to extract:
      - merchant  (str)
      - amount    (float)
      - transaction_date (datetime | None)

    Returns a dict ready to be unpacked into an Expense row.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # ── 1. Merchant ──────────────────────────────────────────
    merchant = "Unknown Merchant"
    if lines:
        merchant = lines[0]
        # Skip generic header lines and very short strings
        noise = {"tax invoice", "bill of supply", "invoice", "receipt", "welcome", "gstin"}
        if len(merchant) < 3 or merchant.lower() in noise:
            if len(lines) > 1:
                merchant = lines[1]

    # ── 2. Amount ────────────────────────────────────────────
    amount_patterns = [
        r"(?:grand\s+)?total(?:\s+due)?(?:\s+amount)?[\s\:\-]*\s*(?:inr|rs\.?|rupees)?\s*([\d\.,]+)",
        r"(?:amount|total\s+paid|paid\s+amount|amount\s+received)[\s\:\-]*\s*(?:inr|rs\.?|rupees)?\s*([\d\.,]+)",
        r"(?:inr|rs\.?)\s*([\d\.,]+)",
        r"due[\s\:\-]*\s*(?:inr|rs\.?|rupees)?\s*([\d\.,]+)",
    ]

    found_amount: Optional[float] = None
    for pattern in amount_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            for match in reversed(matches):
                cleaned = match.replace(",", "")
                try:
                    val = float(cleaned)
                    if val > 0:
                        found_amount = val
                        break
                except ValueError:
                    continue
        if found_amount is not None:
            break

    # Fallback: take the largest decimal number on the receipt
    if found_amount is None:
        numbers = re.findall(r'\b\d+\.\d{2}\b', text)
        floats = []
        for num in numbers:
            try:
                floats.append(float(num))
            except ValueError:
                continue
        if floats:
            found_amount = max(floats)

    amount = found_amount if found_amount is not None else 0.0

    # ── 3. Transaction Date ───────────────────────────────────
    transaction_date: Optional[datetime] = None
    for pattern in _DATE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for raw_date in matches:
            parsed = _parse_date_string(raw_date)
            if parsed:
                transaction_date = parsed
                break
        if transaction_date:
            break

    if transaction_date:
        logger.debug(f"Extracted transaction_date: {transaction_date}")
    else:
        logger.debug("No date found in OCR text — transaction_date will be None.")

    return {
        "merchant": merchant,
        "amount": amount,
        "transaction_date": transaction_date,
    }
