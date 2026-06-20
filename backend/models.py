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
    merchant = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    category = Column(String, default="Uncategorized", nullable=False)
    transaction_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to receipt
    receipt = relationship("Receipt", back_populates="expense")
