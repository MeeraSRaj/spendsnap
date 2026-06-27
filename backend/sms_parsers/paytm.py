import re
from datetime import datetime
from typing import Dict, Any, Optional
from backend.sms_parsers.base import SMSParser

class PaytmParser(SMSParser):
    def __init__(self):
        super().__init__("Paytm")

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        # Check if text is Paytm related
        is_paytm = "paytm" in text.lower() or "paid rs" in text.lower() or "sent rs" in text.lower()
        if not is_paytm:
            return None

        # Example: "Paid Rs. 350.00 to SWIGGY. Wallet Bal: Rs 120. TxnId: 102938"
        # Example: "Sent Rs. 40.00 to CANTEEN from Paytm Payments Bank. Ref: 2039281"

        # 1. Extract Amount
        amount_match = re.search(r"(?:Paid|Sent)\s+(?:Rs\.?|INR)\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if not amount_match:
            # Fallback to general Rs amount
            amount_match = re.search(r"(?:Rs\.?|INR)\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
            if not amount_match:
                return None
        amount = self.clean_amount(amount_match.group(1))

        # 2. Extract Merchant
        merchant = "Paytm Transaction"
        merchant_match = re.search(r"to\s+([^from\.\,]+?)(?:\s+from|\s+wallet|\s+bal|\.|\,|$)", text, re.IGNORECASE)
        if merchant_match:
            merchant = merchant_match.group(1).strip()

        # Simplify merchant
        if "Ref" in merchant:
            merchant = merchant.split("Ref")[0].strip()

        # 3. Extract Date (Paytm SMS might not have date, if missing we return current date or try to match)
        transaction_date = None
        date_match = re.search(r"on\s+(\d{2}[-/]\d{2}[-/]\d{2,4})", text, re.IGNORECASE)
        if date_match:
            date_str = date_match.group(1)
            formats = ["%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"]
            transaction_date = self.parse_datetime(date_str, formats)
        else:
            # Fallback to current time
            transaction_date = datetime.now()

        return {
            "merchant": merchant,
            "amount": amount,
            "transaction_date": transaction_date
        }
