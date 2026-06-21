from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base

class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, nullable=False)
    raw_text = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to expenses (a receipt extracts to an expense)
    expense = relationship("Expense", back_populates="receipt", uselist=False, cascade="all, delete-orphan")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=True)

    # Core parsed fields
    merchant = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    category = Column(String, default="Uncategorized", nullable=False)

    # Actual date from the receipt/SMS (not upload time)
    transaction_date = Column(DateTime(timezone=True), nullable=True)

    # Input source — lets users trace back to the original artefact
    # Values: "photo" | "screenshot" | "pdf" | "sms"
    source_type = Column(String, default="photo", nullable=False)

    # AI categorisation fields (populated in Phase 3 when Claude is integrated)
    ai_suggested_category = Column(String, nullable=True)
    category_confidence = Column(Float, nullable=True)  # 0.0–1.0

    # User isolation stub — nullable until auth is wired up in Phase 2
    user_id = Column(String, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to receipt
    receipt = relationship("Receipt", back_populates="expense")
