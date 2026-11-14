import hashlib
import re
import unicodedata


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_SIG_RE = re.compile(
    r"(--\s*\n.*$|sent from my .*$|trân trọng,.*$|best regards,.*$)",
    re.IGNORECASE | re.DOTALL,
)
_WHITESPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\sÀ-ỹ]", re.UNICODE)


def strip_vietnamese_diacritics(text: str) -> str:
    """Remove Vietnamese accents while converting đ/Đ cleanly for fuzzy matching."""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped)


def clean_text(raw: str) -> str:
    """Step 1 preprocessing: NFC normalize, strip HTML/URLs/noise, collapse whitespace."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFC", raw)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _EMAIL_SIG_RE.sub(" ", text)
    text = text.replace("\u200b", " ").replace("\xa0", " ")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def normalize_for_embedding(title: str, content: str) -> str:
    """Combine title and content into clean canonical text for vectorization."""
    t = clean_text(title)
    c = clean_text(content)
    if t and c:
        if t.lower() in c.lower():
            return c
        return f"{t}. {c}"
    return t or c


def exact_normalized_hash(text: str) -> str:
    """Produce stable hash on lowercase punctuation-stripped text to detect exact duplicates."""
    canonical = strip_vietnamese_diacritics(clean_text(text).lower())
    canonical = _NON_WORD_RE.sub(" ", canonical)
    canonical = _WHITESPACE_RE.sub(" ", canonical).strip()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_empty_feedback(title: str, content: str) -> bool:
    combined = normalize_for_embedding(title, content)
    return len(combined.strip()) < 3
