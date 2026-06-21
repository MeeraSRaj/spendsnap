import os
import shutil
import uuid
import logging
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from backend.config import settings
from backend.database import engine, get_db, Base
from backend.models import Receipt, Expense
from backend.schemas import ExpenseResponse, ExpenseUpdate, UploadResponse
from backend.ocr import perform_ocr, parse_receipt_text, extract_pdf_text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spendsnap.main")

# Auto-create database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SpendSnap AI API",
    description="Your Financial Memory — Core Pipeline API",
    version="1.1.0"
)

# Configure CORS — restrict origins in production via CORS_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Utility helpers
# ──────────────────────────────────────────────

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PDF_EXTENSIONS   = {".pdf"}
ALLOWED_EXTENSIONS       = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS


def _detect_source_type(filename: str) -> str:
    """
    Infer a best-guess source_type from the filename.
    Users (or the mobile client) can override this after upload.
    """
    fn = (filename or "").lower()
    if fn.endswith(".pdf"):
        return "pdf"
    # Common UPI app screenshot naming conventions
    if any(kw in fn for kw in ("screenshot", "screen_shot", "upi", "phonepe", "gpay", "paytm", "bhim")):
        return "screenshot"
    return "photo"


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

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
        "database_type": "PostgreSQL" if settings.is_postgres else "SQLite",
        "max_upload_mb": settings.MAX_UPLOAD_SIZE_MB,
    }


@app.post("/api/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Validate file extension
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 2. Enforce file size limit (read into memory once, reuse bytes)
    file_bytes = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit. "
                   f"Received {len(file_bytes) / (1024*1024):.1f} MB."
        )

    # 3. Save the uploaded file locally with a unique name
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save receipt file."
        )

    # 4. Extract raw text — branch on image vs PDF
    try:
        if ext in ALLOWED_PDF_EXTENSIONS:
            raw_text = extract_pdf_text(file_bytes, filename=file.filename)
        else:
            raw_text = perform_ocr(file_bytes, filename=file.filename)
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text extraction failed: {str(e)}"
        )

    # 5. Parse extracted text → merchant, amount, transaction_date
    parsed_info = parse_receipt_text(raw_text)

    # 6. Infer source_type from filename heuristics
    source_type = _detect_source_type(file.filename or "")

    try:
        # 7. Persist Receipt record
        db_receipt = Receipt(
            file_path=file_path,
            raw_text=raw_text
        )
        db.add(db_receipt)
        db.commit()
        db.refresh(db_receipt)

        # 8. Persist linked Expense record with all parsed + derived fields
        db_expense = Expense(
            receipt_id=db_receipt.id,
            merchant=parsed_info["merchant"],
            amount=parsed_info["amount"],
            transaction_date=parsed_info["transaction_date"],  # OCR-extracted date
            category="Uncategorized",
            source_type=source_type,
        )
        db.add(db_expense)
        db.commit()
        db.refresh(db_expense)

        logger.info(
            f"Processed upload: [{source_type}] {db_expense.merchant} "
            f"₹{db_expense.amount} on {db_expense.transaction_date or 'unknown date'}"
        )

        return {
            "receipt": db_receipt,
            "expense": db_expense
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction failed: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed: {str(e)}"
        )


@app.get("/api/expenses", response_model=List[ExpenseResponse])
def get_expenses(db: Session = Depends(get_db)):
    # Return expenses ordered by transaction_date (OCR date) or created_at as fallback
    return (
        db.query(Expense)
        .order_by(
            Expense.transaction_date.desc().nullslast(),
            Expense.created_at.desc()
        )
        .all()
    )


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

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_expense, key, value)

    try:
        db.commit()
        db.refresh(db_expense)
        logger.info(
            f"Expense {expense_id} updated: merchant={db_expense.merchant}, "
            f"amount={db_expense.amount}, category={db_expense.category}"
        )
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
        # Clean up the physical file from disk if it exists
        if db_expense.receipt and db_expense.receipt.file_path:
            if os.path.exists(db_expense.receipt.file_path):
                os.remove(db_expense.receipt.file_path)

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
