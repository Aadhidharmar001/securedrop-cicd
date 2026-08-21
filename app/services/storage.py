from pathlib import Path
from uuid import uuid4

UPLOAD_DIR = Path("uploads")

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def generate_stored_filename(original_filename: str) -> str:
    extension = Path(original_filename).suffix.lower()
    return f"{uuid4().hex}{extension}"


def validate_file(filename: str, file_size: int) -> None:
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"File type '{extension}' is not allowed."
        )

    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            "File size exceeds the 10 MB limit."
        )


def save_file(file_content: bytes, stored_filename: str) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    file_path = UPLOAD_DIR / stored_filename
    file_path.write_bytes(file_content)

    return file_path