"""Chunking strategies for document processing and RAG indexing."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ingestion.models import Chunk, Document


def estimate_tokens(text: str) -> int:
    """Estimates token count with character and whitespace heuristic (~4 chars/token)."""
    if not text:
        return 0
    words = len(text.split())
    chars = len(text)
    # Balanced heuristic approximating typical BPE / cl100k / LLaMA tokenizers
    return max(1, int((words * 1.25 + chars / 3.8) / 2))


class BaseChunker:
    """Base interface for document chunkers."""

    def split_document(self, document: Document) -> List[Chunk]:
        raise NotImplementedError

    def split_documents(self, documents: List[Document]) -> List[Chunk]:
        all_chunks: List[Chunk] = []
        for doc in documents:
            all_chunks.extend(self.split_document(doc))
        return all_chunks


class RecursiveCharacterChunker(BaseChunker):
    """
    Recursively splits text using a hierarchy of separators (paragraphs, newlines, sentences, words)
    to keep semantic blocks cohesive while adhering to chunk_size and chunk_overlap constraints.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Optional[List[str]] = None,
    ) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError(f"chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively splits text until chunks are <= chunk_size."""
        final_chunks: List[str] = []

        # Find the first separator present in text
        separator = separators[-1]
        new_separators: List[str] = []
        for i, sep in enumerate(separators):
            if sep == "":
                separator = ""
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1:]
                break

        splits = text.split(separator) if separator else list(text)

        current_doc: List[str] = []
        total_len = 0

        for piece in splits:
            piece_len = len(piece) + (len(separator) if current_doc else 0)

            if total_len + piece_len <= self.chunk_size:
                current_doc.append(piece)
                total_len += piece_len
            else:
                if current_doc:
                    merged = separator.join(current_doc)
                    final_chunks.append(merged)

                    # Build overlap window from tail
                    overlap_doc: List[str] = []
                    overlap_len = 0
                    for prev in reversed(current_doc):
                        p_len = len(prev) + (len(separator) if overlap_doc else 0)
                        if overlap_len + p_len <= self.chunk_overlap:
                            overlap_doc.insert(0, prev)
                            overlap_len += p_len
                        else:
                            break
                    current_doc = overlap_doc
                    total_len = overlap_len

                # If the single piece itself is larger than chunk_size, split further
                if len(piece) > self.chunk_size:
                    if new_separators:
                        sub_chunks = self._split_text(piece, new_separators)
                        final_chunks.extend(sub_chunks)
                    else:
                        final_chunks.append(piece)
                else:
                    current_doc.append(piece)
                    total_len += len(piece) + (len(separator) if len(current_doc) > 1 else 0)

        if current_doc:
            final_chunks.append(separator.join(current_doc))

        return [c.strip() for c in final_chunks if c.strip()]

    def split_document(self, document: Document) -> List[Chunk]:
        raw_chunks = self._split_text(document.content, self.separators)
        chunks: List[Chunk] = []

        for idx, text in enumerate(raw_chunks):
            meta = dict(document.metadata)
            meta["chunk_index"] = idx
            meta["chunk_total"] = len(raw_chunks)
            meta["char_length"] = len(text)

            chunk = Chunk(
                content=text,
                doc_id=document.doc_id,
                chunk_index=idx,
                token_count=estimate_tokens(text),
                metadata=meta,
            )
            chunks.append(chunk)

        return chunks


class MarkdownHeaderChunker(BaseChunker):
    """
    Splits Markdown by structural headers (# H1, ## H2, ### H3),
    preserving header hierarchy in metadata for context-aware retrieval.
    """

    HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def __init__(self, max_chunk_size: int = 800, chunk_overlap: int = 100) -> None:
        self.max_chunk_size = max_chunk_size
        self.sub_chunker = RecursiveCharacterChunker(
            chunk_size=max_chunk_size, chunk_overlap=chunk_overlap
        )

    def split_document(self, document: Document) -> List[Chunk]:
        lines = document.content.splitlines()
        sections: List[Dict[str, Any]] = []
        current_header: str = "Introduction"
        current_level: int = 0
        current_lines: List[str] = []

        for line in lines:
            match = self.HEADER_PATTERN.match(line)
            if match:
                if current_lines:
                    sections.append({
                        "header": current_header,
                        "level": current_level,
                        "text": "\n".join(current_lines).strip()
                    })
                    current_lines = []
                current_level = len(match.group(1))
                current_header = match.group(2).strip()
            else:
                current_lines.append(line)

        if current_lines:
            sections.append({
                "header": current_header,
                "level": current_level,
                "text": "\n".join(current_lines).strip()
            })

        chunks: List[Chunk] = []
        chunk_idx = 0

        for sec in sections:
            sec_text = sec["text"]
            if not sec_text:
                continue

            sec_meta = dict(document.metadata)
            sec_meta["section_header"] = sec["header"]
            sec_meta["section_level"] = sec["level"]

            if len(sec_text) <= self.max_chunk_size:
                chunk = Chunk(
                    content=f"## {sec['header']}\n\n{sec_text}",
                    doc_id=document.doc_id,
                    chunk_index=chunk_idx,
                    token_count=estimate_tokens(sec_text),
                    metadata=sec_meta,
                )
                chunks.append(chunk)
                chunk_idx += 1
            else:
                sub_doc = Document(content=sec_text, metadata=sec_meta, doc_id=document.doc_id)
                sub_chunks = self.sub_chunker.split_document(sub_doc)
                for sc in sub_chunks:
                    sc.chunk_index = chunk_idx
                    sc.content = f"## {sec['header']}\n\n{sc.content}"
                    sc.metadata["section_header"] = sec["header"]
                    chunks.append(sc)
                    chunk_idx += 1

        return chunks
