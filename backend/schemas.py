from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Literal

# ──────────────────────────────────────────────
# Expense Schemas
# ──────────────────────────────────────────────

SourceType = Literal["photo", "screenshot", "pdf", "sms"]

class ExpenseBase(BaseModel):
    merchant: str
    amount: float
    category: str = "Uncategorized"
    transaction_date: Optional[datetime] = None
    source_type: SourceType = "photo"

class ExpenseCreate(ExpenseBase):
    receipt_id: Optional[int] = None
    user_id: Optional[str] = None

class ExpenseUpdate(BaseModel):
    merchant: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    transaction_date: Optional[datetime] = None
    source_type: Optional[SourceType] = None

class ExpenseResponse(ExpenseBase):
    id: int
    receipt_id: Optional[int] = None
    source_type: SourceType
    ai_suggested_category: Optional[str] = None
    category_confidence: Optional[float] = None
    user_id: Optional[str] = None
    created_at: datetime

    # Enable ORM integration
    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────
# Receipt Schemas
# ──────────────────────────────────────────────

class ReceiptResponse(BaseModel):
    id: int
    file_path: str
    raw_text: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────
# Compound response for the receipt upload endpoint
# ──────────────────────────────────────────────

class UploadResponse(BaseModel):
    receipt: ReceiptResponse
    expense: ExpenseResponse


# ──────────────────────────────────────────────
# SMS parsing request schema
# ──────────────────────────────────────────────

class SMSPayload(BaseModel):
    sms_text: str
