"""Security utilities"""
import re
from pathlib import Path


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection"""
    # Remove null bytes
    text = text.replace("\x00", "")
    # Limit length
    if len(text) > 50000:
        text = text[:50000] + "... [truncated]"
    return text


def validate_file_upload(filename: str, max_size_mb: int = 50) -> tuple:
    """Validate uploaded file"""
    # Check for path traversal
    if ".." in filename or filename.startswith("/"):
        return False, "Invalid filename: path traversal detected"

    # Check extension
    allowed = [
        ".py", ".js", ".html", ".css", ".json", ".xml", ".yaml", ".yml",
        ".md", ".txt", ".csv", ".sh", ".sql", ".png", ".jpg", ".jpeg",
        ".gif", ".webp", ".pdf", ".docx", ".xlsx", ".pptx"
    ]
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        return False, f"File type {ext} not allowed"

    return True, ""
