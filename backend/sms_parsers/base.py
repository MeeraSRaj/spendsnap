import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("spendsnap.sms_parsers")

class SMSParser:
    def __init__(self, bank_name: str):
        self.bank_name = bank_name

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parses raw SMS text and returns a dict containing:
          - 'amount': float
          - 'merchant': str
          - 'transaction_date': datetime | None
        Returns None if the SMS does not match this parser's format.
        """
        raise NotImplementedError("Subclasses must implement parse()")

    def clean_amount(self, amt_str: str) -> float:
        """Converts raw amount string to float."""
        try:
            # Remove commas and any other non-numeric chars except dot
            cleaned = re.sub(r"[^\d\.]", "", amt_str)
            return float(cleaned)
        except ValueError:
            return 0.0

    def parse_datetime(self, date_str: str, formats: list) -> Optional[datetime]:
        """Tries to parse date string with various formats."""
        date_str = date_str.strip()
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
