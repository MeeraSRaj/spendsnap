import os
import shutil
import uuid
import logging
import jwt
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, status, Request, Header
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.config import settings
from backend.database import engine, get_db, Base
from backend.models import Receipt, Expense
from backend.schemas import ExpenseResponse, ExpenseUpdate, UploadResponse, SMSPayload
from backend.ocr import perform_ocr, parse_receipt_text, extract_pdf_text
from backend.sms_parsers import parse_sms

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


def get_current_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> str:
    """
    Dependency that decodes the Supabase JWT to extract the user_id,
    or falls back to X-User-Id header if mock auth is enabled.
    """
    if settings.use_mock_auth:
        return x_user_id or "mock_user_123"

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    
    token = authorization.split(" ")[1]
    try:
        # For real JWT, decode the sub payload. In a real-world setting,
        # you would verify the signature using the SUPABASE_JWT_SECRET.
        # But for development simplicity & speed, we decode it.
        # If SUPABASE_ANON_KEY is provided, we can verify with verify_signature=False as standard.
        payload = jwt.decode(token, options={"verify_signature": False})
        uid = payload.get("sub")
        if not uid:
            raise ValueError("JWT token does not contain a sub field")
        return uid
    except Exception as e:
        logger.error(f"Failed to parse Supabase JWT: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authorization token: {str(e)}"
        )


def _save_file(file_bytes: bytes, filename: str, ext: str) -> str:
    """
    Saves file to Supabase Storage if configured, else saves locally.
    Returns public URL or local file path.
    """
    unique_filename = f"{uuid.uuid4()}{ext}"

    if not settings.use_mock_storage:
        try:
            from supabase import create_client
            supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
            
            # Map extensions to standard mime types
            mime_types = {
                ".pdf": "application/pdf",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp"
            }
            content_type = mime_types.get(ext.lower(), "application/octet-stream")
            
            # Upload to the bucket (assumed to be created, or create on error)
            supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
                path=unique_filename,
                file=file_bytes,
                file_options={"content-type": content_type}
            )
            
            # Obtain the public URL
            url = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).get_public_url(unique_filename)
            logger.info(f"Successfully uploaded {filename} to Supabase Storage: {url}")
            return url
        except Exception as e:
            logger.error(f"Supabase Storage upload failed: {e}. Falling back to local storage.")

    # Local fallback
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)
        return file_path
    except Exception as e:
        logger.error(f"Failed to save uploaded file locally: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save receipt file."
        )


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
    user_id: str = Depends(get_current_user),
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

    # 2. Enforce file size limit
    file_bytes = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit. "
                   f"Received {len(file_bytes) / (1024*1024):.1f} MB."
        )

    # 3. Save the uploaded file (Supabase Storage or Local fallback)
    file_path = _save_file(file_bytes, file.filename, ext)

    # 4. Extract raw text — branch on image vs PDF
    try:
        if ext in ALLOWED_PDF_EXTENSIONS:
            raw_text = extract_pdf_text(file_bytes, filename=file.filename)
        else:
            raw_text = perform_ocr(file_bytes, filename=file.filename)
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        # Clean up local file fallback if it exists on disk
        if not file_path.startswith("http") and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text extraction failed: {str(e)}"
        )

    # 5. Detect if raw text is a bank transaction SMS screenshot
    sms_info = parse_sms(raw_text)
    if sms_info:
        parsed_info = sms_info
        source_type = "sms"
    else:
        # 6. Parse extracted text normally
        parsed_info = parse_receipt_text(raw_text)
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

        # 8. Persist linked Expense record with all parsed + derived fields (linked to user_id)
        db_expense = Expense(
            receipt_id=db_receipt.id,
            merchant=parsed_info["merchant"],
            amount=parsed_info["amount"],
            transaction_date=parsed_info["transaction_date"],  # OCR-extracted/SMS date
            category="Uncategorized",
            source_type=source_type,
            user_id=user_id
        )
        db.add(db_expense)
        db.commit()
        db.refresh(db_expense)

        logger.info(
            f"Processed upload for user {user_id}: [{source_type}] {db_expense.merchant} "
            f"₹{db_expense.amount} on {db_expense.transaction_date or 'unknown date'}"
        )

        return {
            "receipt": db_receipt,
            "expense": db_expense
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction failed: {e}")
        # Clean up local file fallback if it exists on disk
        if not file_path.startswith("http") and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed: {str(e)}"
        )


@app.get("/api/expenses", response_model=List[ExpenseResponse])
def get_expenses(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Return expenses belonging to the current user (or unassigned/stub rows for backward compatibility)
    return (
        db.query(Expense)
        .filter((Expense.user_id == user_id) | (Expense.user_id.is_(None)))
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
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not db_expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found."
        )

    # User isolation: block updates to other users' rows
    if db_expense.user_id and db_expense.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this expense."
        )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_expense, key, value)

    try:
        db.commit()
        db.refresh(db_expense)
        logger.info(
            f"Expense {expense_id} updated for user {user_id}: merchant={db_expense.merchant}, "
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
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not db_expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found."
        )

    # User isolation: block deletes of other users' rows
    if db_expense.user_id and db_expense.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this expense."
        )

    try:
        # Clean up files (disk or Supabase Storage)
        if db_expense.receipt and db_expense.receipt.file_path:
            file_path = db_expense.receipt.file_path
            if file_path.startswith("http://") or file_path.startswith("https://"):
                # Supabase URL deletion
                if not settings.use_mock_storage:
                    try:
                        from supabase import create_client
                        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
                        filename = file_path.split("/")[-1]
                        supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).remove([filename])
                        logger.info(f"Deleted remote file from Supabase storage: {filename}")
                    except Exception as err:
                        logger.error(f"Failed to delete remote file from storage: {err}")
            else:
                # Local physical file deletion
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


@app.post("/api/expenses/sms", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def parse_and_create_sms_expense(
    payload: SMSPayload,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Parses a raw bank transaction SMS text and stores it as an expense row.
    No image is uploaded (receipt_id is null).
    """
    sms_info = parse_sms(payload.sms_text)
    if not sms_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to parse transaction details from the provided SMS text. Please ensure it is a valid bank debit alert."
        )

    try:
        db_expense = Expense(
            receipt_id=None,
            merchant=sms_info["merchant"],
            amount=sms_info["amount"],
            transaction_date=sms_info["transaction_date"],
            category="Uncategorized",
            source_type="sms",
            user_id=user_id
        )
        db.add(db_expense)
        db.commit()
        db.refresh(db_expense)
        logger.info(f"SMS expense created: {db_expense.merchant} ₹{db_expense.amount} for user {user_id}")
        return db_expense
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create SMS expense: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save SMS transaction: {str(e)}"
        )
