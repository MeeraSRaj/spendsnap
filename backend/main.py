import os
import shutil
import uuid
import logging
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from backend.config import settings
from backend.database import engine, get_db, Base
from backend.models import Receipt, Expense
from backend.schemas import ExpenseResponse, ExpenseUpdate, UploadResponse
from backend.ocr import perform_ocr, parse_receipt_text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spendsnap.main")

# Auto-create database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SpendSnap AI API",
    description="Your Financial Memory - Month 1 Core Pipeline API",
    version="1.0.0"
)

# Configure CORS so local Expo app can make API requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def read_root():
    try:
        with open(os.path.join(settings.BASE_DIR, "index.html"), "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except Exception as e:
        logger.error(f"Failed to load index.html template: {e}")
        return HTMLResponse(
            content=f"<h1>SpendSnap AI Dashboard Offline</h1><p>Error loading dashboard templates: {str(e)}</p>",
            status_code=500
        )


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "mock_ocr": settings.use_mock_ocr,
        "database_type": "PostgreSQL" if settings.is_postgres else "SQLite"
    }

@app.post("/api/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Validate file extension
    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format. Supported formats: {', '.join(allowed_extensions)}"
        )

    # 2. Save the uploaded file locally with a unique name
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save receipt image."
        )

    # 3. Read image bytes and run OCR
    try:
        with open(file_path, "rb") as image_file:
            image_bytes = image_file.read()
        
        raw_text = perform_ocr(image_bytes, filename=file.filename)
    except Exception as e:
        logger.error(f"OCR processing failed: {e}")
        # Clean up saved file if OCR fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR engine failed: {str(e)}"
        )

    # 4. Parse extracted text using Regex
    parsed_info = parse_receipt_text(raw_text)

    try:
        # 5. Save Receipt into DB
        # Convert path to relative or keep absolute path
        db_receipt = Receipt(
            file_path=file_path,
            raw_text=raw_text
        )
        db.add(db_receipt)
        db.commit()
        db.refresh(db_receipt)

        # 6. Save Expense into DB linked to receipt
        db_expense = Expense(
            receipt_id=db_receipt.id,
            merchant=parsed_info["merchant"],
            amount=parsed_info["amount"],
            category="Uncategorized"
        )
        db.add(db_expense)
        db.commit()
        db.refresh(db_expense)

        logger.info(f"Successfully processed upload: {db_expense.merchant} - Rs. {db_expense.amount}")
        
        return {
            "receipt": db_receipt,
            "expense": db_expense
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction failed: {e}")
        # Cleanup file
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed: {str(e)}"
        )

@app.get("/api/expenses", response_model=List[ExpenseResponse])
def get_expenses(db: Session = Depends(get_db)):
    # Return expenses ordered by transaction_date descending
    return db.query(Expense).order_by(Expense.transaction_date.desc()).all()

@app.put("/api/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db)
):
    db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not db_expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found."
        )

    # Update database record attributes if provided in payload
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_expense, key, value)

    try:
        db.commit()
        db.refresh(db_expense)
        logger.info(f"Expense {expense_id} updated: Merchant={db_expense.merchant}, Amount={db_expense.amount}")
        return db_expense
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update expense {expense_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update expense."
        )

@app.delete("/api/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db)
):
    db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not db_expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found."
        )

    try:
        # Also clean up the physical receipt file from disk if present
        if db_expense.receipt:
            file_path = db_expense.receipt.file_path
            if os.path.exists(file_path):
                os.remove(file_path)

        db.delete(db_expense)
        db.commit()
        logger.info(f"Expense {expense_id} and associated files deleted.")
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete expense {expense_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete expense."
        )
