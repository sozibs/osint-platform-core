"""Text normalization utilities for OSINT entity names and addresses."""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, Optional

_WHITESPACE_RE = re.compile(r"\s+")
_SPECIAL_CHAR_RE = re.compile(r"[^\w\s]", re.UNICODE)
_ORG_SUFFIXES = re.compile(
    r"\s*(?:,?\s*)(?:Inc\.?|LLC\.?|Ltd\.?|Limited|Corp\.?|Corporation|"
    r"GmbH|AG|S\.A\.?|B\.V\.?|Pty\.?|PLC\.?|LLP\.?|LP\.?|Co\.?)\s*$",
    re.IGNORECASE,
)
_NAME_PARTICLES = {"van", "de", "di", "da", "del", "della", "le", "la", "von", "bin", "binti"}

# Simple language detection keyword sets
_LANG_HINTS: Dict[str, list] = {
    "es": ["de", "la", "el", "en", "que", "un", "una", "los", "las", "es"],
    "fr": ["le", "la", "les", "de", "du", "et", "un", "une", "que", "est"],
    "de": ["der", "die", "das", "und", "ist", "von", "mit", "für", "auf"],
    "it": ["il", "lo", "la", "i", "gli", "le", "di", "da", "in", "con"],
    "pt": ["o", "a", "os", "as", "de", "do", "da", "em", "um", "uma"],
}


def normalize_name(name: str) -> str:
    """Normalize a person or entity name to Title Case with collapsed whitespace."""
    if not name:
        return name
    name = normalize_unicode(name)
    name = _WHITESPACE_RE.sub(" ", name).strip()
    # Title-case, preserving known particles in lowercase
    words = name.split()
    result = []
    for i, word in enumerate(words):
        lower = word.lower()
        if i > 0 and lower in _NAME_PARTICLES:
            result.append(lower)
        else:
            result.append(word.capitalize())
    return " ".join(result)


def normalize_organization_name(name: str) -> str:
    """Remove common legal suffixes and normalize whitespace."""
    if not name:
        return name
    name = normalize_unicode(name)
    name = _ORG_SUFFIXES.sub("", name)
    return _WHITESPACE_RE.sub(" ", name).strip()


def extract_name_parts(full_name: str) -> Dict[str, Optional[str]]:
    """Split a full name into first, middle, and last components.

    Handles common Western name patterns. Returns a dict with keys
    ``first``, ``middle``, and ``last`` (all Optional[str]).
    """
    if not full_name:
        return {"first": None, "middle": None, "last": None}

    parts = _WHITESPACE_RE.sub(" ", full_name.strip()).split()
    if len(parts) == 1:
        return {"first": parts[0], "middle": None, "last": None}
    if len(parts) == 2:
        return {"first": parts[0], "middle": None, "last": parts[1]}
    # Check for name particles
    if len(parts) >= 3:
        if parts[1].lower() in _NAME_PARTICLES:
            return {
                "first": parts[0],
                "middle": None,
                "last": " ".join(parts[1:]),
            }
        return {
            "first": parts[0],
            "middle": " ".join(parts[1:-1]),
            "last": parts[-1],
        }
    return {"first": parts[0], "middle": None, "last": parts[-1]}


def normalize_address(address: str) -> str:
    """Collapse whitespace and normalize casing for an address string."""
    if not address:
        return address
    address = normalize_unicode(address)
    address = _WHITESPACE_RE.sub(" ", address).strip()
    return address


def remove_special_chars(text: str, keep_chars: str = "") -> str:
    """Remove non-alphanumeric characters from *text*, optionally keeping *keep_chars*."""
    if keep_chars:
        pattern = re.compile(f"[^\\w\\s{re.escape(keep_chars)}]", re.UNICODE)
    else:
        pattern = _SPECIAL_CHAR_RE
    return pattern.sub("", text)


def normalize_unicode(text: str) -> str:
    """Apply NFC Unicode normalization and strip zero-width characters."""
    text = unicodedata.normalize("NFC", text)
    # Remove zero-width and control characters
    text = "".join(c for c in text if not unicodedata.category(c).startswith("C"))
    return text


def detect_language(text: str) -> str:
    """Simple heuristic language detection by common function words.

    Returns an ISO 639-1 code, defaulting to 'en'.
    """
    words = set(re.findall(r"\b[a-z]{2,6}\b", text.lower()))
    best_lang = "en"
    best_score = 0
    for lang, hints in _LANG_HINTS.items():
        score = sum(1 for h in hints if h in words)
        if score > best_score:
            best_score = score
            best_lang = lang
    return best_lang


def transliterate(text: str, target_script: str = "latin") -> str:
    """Transliterate non-Latin text to ASCII via Unicode decomposition.

    Only basic NFD-based transliteration is performed. For production use,
    a library like ``Unidecode`` would provide higher quality.
    """
    if target_script != "latin":
        return text
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")
