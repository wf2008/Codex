"""Smart file processing for uploaded files"""
import os
import json
import csv
import io
from pathlib import Path
from config import WORKSPACE


def process_uploaded_file(file_obj, filename: str = None) -> str:
    """Process any uploaded file and return relevant content"""
    if filename is None:
        filename = getattr(file_obj, "name", "unknown")

    ext = Path(filename).suffix.lower()
    content = ""

    try:
        if ext in [".py", ".js", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".toml", ".md", ".txt", ".sh", ".sql"]:
            # Text files - read as text
            content = file_obj.read().decode("utf-8", errors="replace")
            return f"File: {filename}\nType: {ext}\n\n```\n{content[:5000]}\n```"

        elif ext == ".csv":
            # CSV - parse and summarize
            text = file_obj.read().decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            headers = reader.fieldnames or []
            preview = []
            for i, row in enumerate(rows[:10]):
                preview.append(f"Row {i+1}: {dict(row)}")
            return (
                f"CSV File: {filename}\n"
                f"Columns: {headers}\n"
                f"Total Rows: {len(rows)}\n"
                f"Preview (first 10 rows):\n" + "\n".join(preview)
            )

        elif ext == ".json":
            # JSON - pretty print
            data = json.loads(file_obj.read().decode("utf-8"))
            pretty = json.dumps(data, indent=2, ensure_ascii=False)[:5000]
            return f"JSON File: {filename}\n\n```json\n{pretty}\n```"

        elif ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            # Images - save to workspace and return path
            save_path = Path(WORKSPACE) / filename
            with open(save_path, "wb") as f:
                f.write(file_obj.read())
            return f"Image saved to workspace: {save_path}\nYou can reference it in your code."

        elif ext in [".pdf", ".docx", ".xlsx", ".pptx"]:
            return f"Document uploaded: {filename}\nType: {ext}\nNote: Document parsing requires additional libraries (PyPDF2, python-docx, etc.)"

        else:
            # Binary - save and report
            save_path = Path(WORKSPACE) / filename
            with open(save_path, "wb") as f:
                f.write(file_obj.read())
            size = os.path.getsize(save_path)
            return f"File saved to workspace: {save_path}\nSize: {size} bytes\nType: {ext}"

    except Exception as e:
        return f"Error processing file {filename}: {e}"


def save_to_workspace(filename: str, content: str) -> str:
    """Save content to workspace file"""
    path = Path(WORKSPACE) / filename
    try:
        path.write_text(content, encoding="utf-8")
        return f"Saved to {path}"
    except Exception as e:
        return f"Save error: {e}"


def list_workspace_files() -> list:
    """List all files in workspace"""
    try:
        return [f.name for f in Path(WORKSPACE).iterdir() if f.is_file()]
    except:
        return []
