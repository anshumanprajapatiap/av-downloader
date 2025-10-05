

import re
import unicodedata

def sanitize_filename(title: str) -> str:
    # Normalize unicode (convert full-width characters to half-width)
    title = unicodedata.normalize("NFKC", title)
    # Remove unsupported/special characters
    title = re.sub(r'[^\w\s\-_.,()\'!&]+', '', title)
    # Replace spaces with underscores
    return "_".join(title.strip().split())

def sanitize_playlist_filename(title: str) -> str:
    """Convert playlist title to safe filename with hash suffix"""
    safe_title = title.strip().replace(" ", "_")
    safe_title = "".join(c for c in safe_title if c.isalnum() or c in "_-")
    short_hash = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{safe_title}_{short_hash}.zip"


