from typing import Dict, Any, Optional
from datetime import datetime
import re

from backend.sms_parsers.hdfc import HDFCParser
from backend.sms_parsers.icici import ICICIParser
from backend.sms_parsers.sbi import SBIParser
from backend.sms_parsers.paytm import PaytmParser
from backend.sms_parsers.base import SMSParser

PARSERS = [
    HDFCParser(),
    ICICIParser(),
    SBIParser(),
    PaytmParser()
]

def parse_sms(text: str) -> Optional[Dict[str, Any]]:
    """
    Tries each bank-specific parser, and if none match, runs a generic fallback parser.
    Returns:
      Dict with 'merchant', 'amount', 'transaction_date' or None.
    """
    # Safety Check: SMS messages are short and compact.
    # Full receipts have multiple itemized lines and are typically much longer.
    if len(text) > 350 or text.count("\n") > 5:
        return None

    # 1. Try bank-specific parsers
    for parser in PARSERS:
        try:
            res = parser.parse(text)
            if res is not None:
                return res
        except Exception as e:
            # Silently continue to next parser
            continue

    # 2. Generic fallback parser (for generic transaction receipts or other banks)
    # Ensure the SMS contains transaction-indicative keywords
    sms_keywords = {"debit", "credit", "spent", "sent", "paid", "received", "txn", "transaction", "alert", "transferred", "deposited"}
    text_lower = text.lower()
    if not any(kw in text_lower for kw in sms_keywords):
        return None

    # Search for standard Rs / INR amount
    amount_match = re.search(r"(?:Rs\.?|INR|Amt)\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if amount_match:
        amount_str = amount_match.group(1).replace(",", "")
        try:
            amount = float(amount_str)
        except ValueError:
            return None

        # Infer merchant name from "at [merchant]" or "to [merchant]"
        merchant = "SMS Transaction"
        merchant_match = re.search(
            r"(?:at|to|info[:\s\*]+)\s+([A-Za-z0-9\s\&\-\*]+?)(?:\s+on|\s+from|\s+using|\.|\b|$)",
            text,
            re.IGNORECASE
        )
        if merchant_match:
            candidate = merchant_match.group(1).strip()
            # Filter noise and validate length
            if 2 <= len(candidate) <= 40:
                merchant = candidate

        # Clean generic merchant noise
        if "*" in merchant:
            merchant = merchant.split("*")[-1].strip()

        # Try to parse date
        transaction_date = None
        date_match = re.search(r"\b(\d{2}[-/]\d{2}[-/]\d{2,4})\b", text)
        if date_match:
            sp = SMSParser("Generic")
            transaction_date = sp.parse_datetime(
                date_match.group(1),
                ["%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"]
            )
        else:
            transaction_date = datetime.now()

        return {
            "merchant": merchant,
            "amount": amount,
            "transaction_date": transaction_date
        }

    return None
