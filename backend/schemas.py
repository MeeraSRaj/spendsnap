from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

# Expense Schemas
class ExpenseBase(BaseModel):
    merchant: str
    amount: float
    category: str = "Uncategorized"
    transaction_date: Optional[datetime] = None

class ExpenseCreate(ExpenseBase):
    receipt_id: Optional[int] = None

class ExpenseUpdate(BaseModel):
    merchant: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    transaction_date: Optional[datetime] = None

class ExpenseResponse(ExpenseBase):
    id: int
    receipt_id: Optional[int] = None
    created_at: datetime
    
    # Enable ORM integration
    model_config = ConfigDict(from_attributes=True)


# Receipt Schemas
class ReceiptResponse(BaseModel):
    id: int
    file_path: str
    raw_text: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Compound response for receipt upload endpoint
class UploadResponse(BaseModel):
    receipt: ReceiptResponse
    expense: ExpenseResponse
