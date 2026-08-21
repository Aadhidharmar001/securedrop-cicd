from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_urlsafe

from fastapi import Depends, FastAPI, File as FastAPIFile, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import File
from .services.storage import (
    generate_stored_filename,
    save_file,
    validate_file,
)


# Create database tables
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="SecureDrop",
    description="Temporary and secure file sharing service",
    version="1.0.0",
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "application": "SecureDrop",
        "version": "1.0.0",
        "status": "running",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


# ============================================================
# UPLOAD FILE
# ============================================================

@app.post("/files")
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    expires_in_hours: int = 24,
    max_downloads: int = 3,
    db: Session = Depends(get_db),
):
    # 1. Validate filename
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required.",
        )

    # 2. Read uploaded file
    file_content = await file.read()
    file_size = len(file_content)

    # 3. Validate file type and size
    try:
        validate_file(
            file.filename,
            file_size,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    # 4. Generate random storage filename
    stored_filename = generate_stored_filename(
        file.filename
    )

    # 5. Save physical file
    try:
        file_path = save_file(
            file_content,
            stored_filename,
        )
    except OSError:
        raise HTTPException(
            status_code=500,
            detail="Failed to store file.",
        )

    # 6. Generate secure share token
    token = token_urlsafe(32)

    # 7. Calculate expiration
    created_at = datetime.now(timezone.utc)

    expires_at = created_at + timedelta(
        hours=expires_in_hours
    )

    # 8. Save metadata to database
    try:
        db_file = File(
            original_filename=file.filename,
            stored_filename=stored_filename,
            token=token,
            file_path=str(file_path),
            file_size=file_size,
            content_type=(
                file.content_type
                or "application/octet-stream"
            ),
            created_at=created_at,
            expires_at=expires_at,
            max_downloads=max_downloads,
            download_count=0,
        )

        db.add(db_file)
        db.commit()
        db.refresh(db_file)

        return {
            "id": db_file.id,
            "filename": db_file.original_filename,
            "share_token": db_file.token,
            "share_url": f"/share/{db_file.token}",
            "expires_at": db_file.expires_at,
            "max_downloads": db_file.max_downloads,
        }

    except Exception:
        db.rollback()

        # If database storage fails,
        # remove the physical file.
        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail="Failed to save file metadata.",
        )


# ============================================================
# LIST FILES
# ============================================================

@app.get("/files")
def list_files(
    db: Session = Depends(get_db),
):
    files = db.query(File).all()

    now = datetime.now(timezone.utc)

    result = []

    for file in files:
        expires_at = file.expires_at

        # SQLite returns naive datetimes.
        # Treat them as UTC.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        # Determine current status
        if expires_at <= now:
            status = "expired"

        elif file.download_count >= file.max_downloads:
            status = "limit_reached"

        else:
            status = "active"

        result.append(
            {
                "id": file.id,
                "filename": file.original_filename,
                "file_size": file.file_size,
                "content_type": file.content_type,
                "created_at": file.created_at,
                "expires_at": file.expires_at,
                "download_count": file.download_count,
                "max_downloads": file.max_downloads,
                "status": status,
            }
        )

    return result


# ============================================================
# DELETE / REVOKE FILE
# ============================================================

@app.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
):
    # 1. Find file metadata
    db_file = (
        db.query(File)
        .filter(File.id == file_id)
        .first()
    )

    if db_file is None:
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    # 2. Get physical file path
    file_path = Path(db_file.file_path)

    # 3. Delete physical file
    if file_path.exists():
        file_path.unlink()

    # 4. Delete database record
    db.delete(db_file)
    db.commit()

    return {
        "message": "File revoked successfully.",
        "file_id": file_id,
    }


# ============================================================
# DOWNLOAD FILE
# ============================================================

@app.get("/share/{token}")
def download_file(
    token: str,
    db: Session = Depends(get_db),
):
    # 1. Find file using share token
    db_file = (
        db.query(File)
        .filter(File.token == token)
        .first()
    )

    if db_file is None:
        raise HTTPException(
            status_code=404,
            detail="Share link not found.",
        )

    # 2. Check expiration
    now = datetime.now(timezone.utc)

    expires_at = db_file.expires_at

    # SQLite may return a naive datetime.
    # Treat it as UTC.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if now >= expires_at:
        raise HTTPException(
            status_code=410,
            detail="Share link has expired.",
        )

    # 3. Check download limit
    if db_file.download_count >= db_file.max_downloads:
        raise HTTPException(
            status_code=410,
            detail="Download limit reached.",
        )

    # 4. Check physical file
    file_path = Path(db_file.file_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File no longer exists.",
        )

    # 5. Increment download count
    db_file.download_count += 1
    db.commit()

    # 6. Return file to user
    return FileResponse(
        path=file_path,
        filename=db_file.original_filename,
        media_type=db_file.content_type,
    )