import re
from datetime import datetime
from typing import Dict, Any, Optional
from backend.sms_parsers.base import SMSParser

class SBIParser(SMSParser):
    def __init__(self):
        super().__init__("SBI")

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        # Check if text is SBI related
        if "sbi" not in text.lower():
            return None

        # Example: "Txn of Rs 500.00 on SBI Debit Card ...1234 at AMAZON on 20Jun26"
        # Example: "Dear Customer, Rs 1,000.00 debited from A/c ...3456 at IndianOil on 20-06-26"

        # 1. Extract Amount
        amount_match = re.search(r"(?:Rs\.?|INR)\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if not amount_match:
            return None
        amount = self.clean_amount(amount_match.group(1))

        # 2. Extract Merchant
        merchant = "SBI Transaction"
        merchant_match = re.search(r"at\s+([^on\.]+?)\s+on", text, re.IGNORECASE)
        if merchant_match:
            merchant = merchant_match.group(1).strip()

        # Simplify merchant
        if "/" in merchant:
            merchant = merchant.split("/")[0]

        # 3. Extract Date
        transaction_date = None
        # Format: on 20Jun26 or on 20-06-26
        date_match = re.search(r"on\s+(\d{2}[-/]?[A-Za-z0-9]{2,3}[-/]?\d{2,4})", text, re.IGNORECASE)
        if date_match:
            date_str = date_match.group(1)
            formats = [
                "%d%b%y", "%d%b%Y", "%d-%b-%y", "%d-%b-%Y",
                "%d-%m-%y", "%d-%m-%Y", "%d/%m/%y", "%d/%m/%Y"
            ]
            transaction_date = self.parse_datetime(date_str, formats)

        return {
            "merchant": merchant,
            "amount": amount,
            "transaction_date": transaction_date
        }
