

import re
import unicodedata

def sanitize_filename(title: str) -> str:
    # Normalize unicode (convert full-width characters to half-width)
    title = unicodedata.normalize("NFKC", title)
    # Remove unsupported/special characters
    title = re.sub(r'[^\w\s\-_.,()\'!&]+', '', title)
    # Replace spaces with underscores
    return "_".join(title.strip().split())