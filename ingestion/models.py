"""Data models for ingestion and processing pipeline."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Document:
    """Represents an ingested document before chunking."""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    doc_id: str = ""

    def __post_init__(self) -> None:
        if not self.doc_id:
            # Generate deterministic doc_id based on source and content hash
            source = str(self.metadata.get("source", "unknown"))
            raw = f"{source}:{self.content}"
            self.doc_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

        if "created_at" not in self.metadata:
            self.metadata["created_at"] = time.time()
        if "char_count" not in self.metadata:
            self.metadata["char_count"] = len(self.content)


@dataclass
class Chunk:
    """Represents a discrete segment of a document ready for embedding and retrieval."""
    content: str
    doc_id: str
    chunk_index: int
    chunk_id: str = ""
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def __post_init__(self) -> None:
        if not self.chunk_id:
            raw = f"{self.doc_id}:{self.chunk_index}:{self.content}"
            self.chunk_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        if not self.token_count:
            # Baseline approximation: 1 token ~= 4 characters or word count * 1.3
            self.token_count = max(1, len(self.content) // 4)


@dataclass
class SearchResult:
    """Represents a retrieved chunk with ranking score."""
    chunk: Chunk
    score: float
    rank: int = 0


@dataclass
class IngestionReport:
    """Summary report of an ingestion run."""
    documents_loaded: int = 0
    chunks_created: int = 0
    total_tokens: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "documents_loaded": self.documents_loaded,
            "chunks_created": self.chunks_created,
            "total_tokens": self.total_tokens,
            "duration_seconds": round(self.duration_seconds, 4),
            "errors": self.errors,
        }
