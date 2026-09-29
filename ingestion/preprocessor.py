"""Text cleaning and normalization utilities for document ingestion."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional


class TextPreprocessor:
    """Preprocesses and normalizes raw text for indexing and LLM consumption."""

    def __init__(
        self,
        normalize_unicode: bool = True,
        remove_control_chars: bool = True,
        collapse_whitespace: bool = True,
        max_consecutive_newlines: int = 2,
    ) -> None:
        self.normalize_unicode = normalize_unicode
        self.remove_control_chars = remove_control_chars
        self.collapse_whitespace = collapse_whitespace
        self.max_consecutive_newlines = max_consecutive_newlines

    def clean(self, text: Optional[str]) -> str:
        """Executes the cleaning pipeline on input text."""
        if not text:
            return ""

        result = text

        # 1. Unicode normalization (NFKC decomposes compatibility chars and recomposes canonically)
        if self.normalize_unicode:
            result = unicodedata.normalize("NFKC", result)

        # 2. Remove control characters (retaining \n, \t, \r)
        if self.remove_control_chars:
            result = "".join(
                ch for ch in result
                if unicodedata.category(ch)[0] != "C" or ch in "\n\t\r"
            )

        # 3. Normalize line breaks to \n
        result = result.replace("\r\n", "\n").replace("\r", "\n")

        # 4. Collapse spaces & tabs on each line
        if self.collapse_whitespace:
            lines = []
            for line in result.split("\n"):
                # Replace multiple inline spaces/tabs with a single space
                clean_line = re.sub(r"[ \t]+", " ", line).strip()
                lines.append(clean_line)
            result = "\n".join(lines)

        # 5. Limit consecutive newlines
        if self.max_consecutive_newlines > 0:
            limit_pattern = rf"\n{{{self.max_consecutive_newlines + 1},}}"
            replacement = "\n" * self.max_consecutive_newlines
            result = re.sub(limit_pattern, replacement, result)

        return result.strip()
