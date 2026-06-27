import re
from datetime import datetime
from typing import Dict, Any, Optional
from backend.sms_parsers.base import SMSParser

class HDFCParser(SMSParser):
    def __init__(self):
        super().__init__("HDFC")

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        # Check if text is HDFC related
        if "hdfc" not in text.lower():
            return None

        # Example: "Alert: Rs 500.00 spent on HDFC Bank Card... at STARBUCKS on 20-06-2026"
        # Example: "HDFC Bank: Rs 349.00 debited from A/c ...1234 at SWIGGY on 20-06-2026"
        
        # 1. Extract Amount
        amount_match = re.search(r"(?:Rs\.?|INR)\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if not amount_match:
            return None
        amount = self.clean_amount(amount_match.group(1))

        # 2. Extract Merchant
        merchant = "HDFC Transaction"
        # Look for "at [Merchant] on" or "info: [Merchant]"
        merchant_match = re.search(r"at\s+([^on]+?)\s+on", text, re.IGNORECASE)
        if merchant_match:
            merchant = merchant_match.group(1).strip()
        else:
            info_match = re.search(r"info[:\s]+([^\s\n]+)", text, re.IGNORECASE)
            if info_match:
                merchant = info_match.group(1).strip()

        # Simplify merchant names like UPI-SWIGGY-1234@okaxis
        if "-" in merchant:
            parts = [p for p in merchant.split("-") if p.upper() not in ("UPI", "DEBIT", "CREDIT", "HDFC")]
            if parts:
                merchant = parts[0]
        if "@" in merchant:
            merchant = merchant.split("@")[0]

        # 3. Extract Date
        transaction_date = None
        date_match = re.search(r"on\s+(\d{2}[-/]\d{2}[-/]\d{2,4})", text, re.IGNORECASE)
        if date_match:
            date_str = date_match.group(1)
            formats = ["%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"]
            transaction_date = self.parse_datetime(date_str, formats)

        return {
            "merchant": merchant,
            "amount": amount,
            "transaction_date": transaction_date
        }
