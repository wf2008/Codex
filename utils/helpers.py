"""General helper utilities"""
import time
import uuid


def truncate_text(text: str, max_length: int = 2000) -> str:
    """Truncate text with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n... [truncated]"


def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 chars for English)"""
    return len(text) // 4


def generate_id() -> str:
    """Generate unique ID"""
    return f"{int(time.time())}_{uuid.uuid4().hex[:8]}"


def format_duration(seconds: float) -> str:
    """Format duration in human readable form"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"
