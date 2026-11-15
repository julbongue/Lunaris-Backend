from __future__ import annotations

import re
import unicodedata


def normalize_identifier(value: str) -> str:
    """Normalize a human-readable site name or ID for tolerant matching.

    Accents are removed, the text is case-folded and every run of
    non-alphanumeric characters is collapsed into a single space.  This makes
    values such as ``"Cratera Shackleton"``, ``"cratera-shackleton"`` and
    ``"CRATERA SHACKLETON"`` resolve to the same key.
    """

    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.casefold()).strip()


def slugify_identifier(value: str) -> str:
    """Return a URL-safe identifier derived from a site name."""

    normalized = normalize_identifier(value)
    return normalized.replace(" ", "-")
