import re
from html import escape


def clean_input(text: str) -> str:
    if not text:
        return ""

    safe_text = escape(text)

    safe_text = re.sub(r'javascript:', '', safe_text, flags=re.IGNORECASE)

    return safe_text.strip()