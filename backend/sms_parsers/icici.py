import re
from datetime import datetime
from typing import Dict, Any, Optional
from backend.sms_parsers.base import SMSParser

class ICICIParser(SMSParser):
    def __init__(self):
        super().__init__("ICICI")

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        # Check if text is ICICI related
        if "icici" not in text.lower():
            return None

        # Example: "Dear Customer, txn of INR 150.00 on ICICI Bank Card ...8920 at AMAZON on 20-Jun-26"
        # Example: "Dear Customer, A/c ...281 debited for INR 2,000.00 on 20-06-26. Info: IPS*FuelStation"

        # 1. Extract Amount
        amount_match = re.search(r"(?:Rs\.?|INR)\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if not amount_match:
            return None
        amount = self.clean_amount(amount_match.group(1))

        # 2. Extract Merchant
        merchant = "ICICI Transaction"
        merchant_match = re.search(r"at\s+([^on\.]+?)\s+(?:on|using)", text, re.IGNORECASE)
        if merchant_match:
            merchant = merchant_match.group(1).strip()
        else:
            info_match = re.search(r"info[:\s\*]+([^\s\n\.]+)", text, re.IGNORECASE)
            if info_match:
                merchant = info_match.group(1).strip()

        # Simplify merchant names
        if "*" in merchant:
            merchant = merchant.split("*")[-1]
        if "/" in merchant:
            merchant = merchant.split("/")[0]

        # 3. Extract Date
        transaction_date = None
        # Try both 20-06-26 / 20-06-2026 AND 20-Jun-26 / 20-Jun-2026 formats
        date_match = re.search(r"on\s+(\d{2}[-/][A-Za-z0-9]{2,3}[-/]\d{2,4})", text, re.IGNORECASE)
        if not date_match:
            # Fallback to general date match in the string
            date_match = re.search(r"\b(\d{2}[-/][A-Za-z0-9]{2,3}[-/]\d{2,4})\b", text, re.IGNORECASE)

        if date_match:
            date_str = date_match.group(1)
            formats = [
                "%d-%b-%y", "%d-%b-%Y", "%d/%b/%y", "%d/%b/%Y",
                "%d-%m-%y", "%d-%m-%Y", "%d/%m/%y", "%d/%m/%Y"
            ]
            transaction_date = self.parse_datetime(date_str, formats)

        return {
            "merchant": merchant,
            "amount": amount,
            "transaction_date": transaction_date
        }
