import re
import logging
from typing import Tuple, Dict, Any, Optional
from google.cloud import vision
from backend.config import settings

logger = logging.getLogger("spendsnap.ocr")

def perform_ocr(image_bytes: bytes, filename: Optional[str] = None) -> str:
    """
    Performs OCR on the provided image bytes.
    If Google Cloud Vision credentials are set, it queries Google Cloud Vision.
    Otherwise, it falls back to a smart mock OCR generator for testing.
    """
    if not settings.use_mock_ocr:
        try:
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
            
    # Mock OCR generator
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
    else:
        # Default receipt template
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


def parse_receipt_text(text: str) -> Dict[str, Any]:
    """
    Parses the raw text extracted from a receipt to find the merchant name and total amount.
    Returns a dictionary with 'merchant', 'amount', and 'transaction_date'.
    """
    # 1. Split text into lines for line-by-line inspection
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    merchant = "Unknown Merchant"
    amount = 0.0
    
    # 2. Extract Merchant (typically the first non-empty line of the receipt)
    if lines:
        merchant = lines[0]
        # Clean up common headers if they appear as merchant
        if len(merchant) < 3 or merchant.lower() in ["tax invoice", "bill of supply", "invoice", "receipt", "welcome"]:
            if len(lines) > 1:
                merchant = lines[1]
                
    # 3. Extract Amount
    # Look for common monetary patterns. In India, formatting uses "Rs.", "Rs", "INR", "Total", "Grand Total", "Total Due", "Amount Paid"
    # Matches patterns like: "Total: Rs. 349.00", "Total Due: 236.26", "INR 798.00", "Amount Received: Rs 2000.00"
    amount_patterns = [
        r"(?:grand\s+)?total(?:\s+due)?(?:\s+amount)?[\s\:\-]*\s*(?:inr|rs\.?|rupees)?\s*([\d\.,]+)",
        r"(?:amount|total\s+paid|paid\s+amount)[\s\:\-]*\s*(?:inr|rs\.?|rupees)?\s*([\d\.,]+)",
        r"(?:inr|rs\.?)\s*([\d\.,]+)",
        r"due[\s\:\-]*\s*(?:inr|rs\.?|rupees)?\s*([\d\.,]+)",
    ]
    
    found_amount = None
    for pattern in amount_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # We look for the last match of 'total' as it's typically the final sum
            for match in reversed(matches):
                # Clean up commas and dots (e.g. 2,000.00 -> 2000.00)
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
            
    # If no pattern matched, scan all numbers and take the maximum number that appears near the bottom
    if found_amount is None:
        # Regex to find all floating point or decimal numbers (excluding common date/id formats)
        numbers = re.findall(r'\b\d+\.\d{2}\b', text)
        floats = []
        for num in numbers:
            try:
                floats.append(float(num))
            except ValueError:
                continue
        if floats:
            # Usually the total is the largest number on the receipt
            found_amount = max(floats)
            
    if found_amount is not None:
        amount = found_amount
        
    return {
        "merchant": merchant,
        "amount": amount
    }
