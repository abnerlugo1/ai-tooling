"""Vector store supporting dense cosine similarity, hybrid BM25 retrieval, and persistence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from ingestion.embeddings import BM25Scorer, BaseEmbedder, LocalDenseEmbedder, cosine_similarity
from ingestion.models import Chunk, SearchResult


class VectorStore:
    """In-memory and disk-persisted vector database for chunks and embeddings."""

    def __init__(
        self,
        embedder: Optional[BaseEmbedder] = None,
        db_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.embedder: BaseEmbedder = embedder or LocalDenseEmbedder()
        self.db_path = Path(db_path) if db_path else None
        self.chunks: List[Chunk] = []
        self._bm25 = BM25Scorer()
        self._bm25_stale = True

        if self.db_path and self.db_path.exists():
            self.load()

    def add_chunks(self, chunks: List[Chunk]) -> int:
        """Adds a list of chunks, computing embeddings if missing."""
        if not chunks:
            return 0

        # Collect chunks needing embedding
        texts_to_embed: List[str] = []
        indices_to_embed: List[int] = []

        for i, chunk in enumerate(chunks):
            if chunk.embedding is None:
                texts_to_embed.append(chunk.content)
                indices_to_embed.append(i)

        if texts_to_embed:
            vectors = self.embedder.embed_batch(texts_to_embed)
            for idx, vec in zip(indices_to_embed, vectors):
                chunks[idx].embedding = vec

        self.chunks.extend(chunks)
        self._bm25_stale = True

        if self.db_path:
            self.save()

        return len(chunks)

    def _ensure_bm25_fitted(self) -> None:
        if self._bm25_stale and self.chunks:
            self._bm25.fit([c.content for c in self.chunks])
            self._bm25_stale = False

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
        hybrid: bool = False,
        alpha: float = 0.7,
    ) -> List[SearchResult]:
        """
        Retrieves top_k relevant chunks for a query.
        If hybrid is True: score = alpha * dense_score + (1 - alpha) * bm25_score.
        """
        if not self.chunks:
            return []

        query_vector = self.embedder.embed_text(query)

        if hybrid:
            self._ensure_bm25_fitted()

        # Compute raw scores
        scored_candidates: List[tuple[Chunk, float]] = []

        # Find max bm25 score for normalization
        bm25_raw_scores: List[float] = []
        if hybrid:
            for i in range(len(self.chunks)):
                bm25_raw_scores.append(self._bm25.score(query, i))
            max_bm25 = max(bm25_raw_scores) if bm25_raw_scores and max(bm25_raw_scores) > 0 else 1.0
        else:
            max_bm25 = 1.0

        for i, chunk in enumerate(self.chunks):
            if filter_fn and not filter_fn(chunk.metadata):
                continue

            dense_score = 0.0
            if chunk.embedding:
                dense_score = cosine_similarity(query_vector, chunk.embedding)

            if hybrid:
                normalized_bm25 = bm25_raw_scores[i] / max_bm25
                # Normalize cosine similarity from [-1, 1] to [0, 1]
                norm_dense = max(0.0, (dense_score + 1.0) / 2.0)
                final_score = alpha * norm_dense + (1.0 - alpha) * normalized_bm25
            else:
                final_score = dense_score

            scored_candidates.append((chunk, final_score))

        # Sort descending by score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        results: List[SearchResult] = []
        for rank, (chunk, score) in enumerate(scored_candidates[:top_k], start=1):
            results.append(SearchResult(chunk=chunk, score=score, rank=rank))

        return results

    def save(self, destination: Optional[Union[str, Path]] = None) -> None:
        """Persists the chunks and vectors to SQLite."""
        save_path = Path(destination) if destination else self.db_path
        if not save_path:
            raise ValueError("No database path specified for save")

        save_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(save_path)
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_json TEXT
                )
            """)
            conn.execute("DELETE FROM chunks")
            rows = [
                (
                    c.chunk_id,
                    c.doc_id,
                    c.chunk_index,
                    c.content,
                    c.token_count,
                    json.dumps(c.metadata, ensure_ascii=False),
                    json.dumps(c.embedding) if c.embedding else None,
                )
                for c in self.chunks
            ]
            conn.executemany(
                "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        conn.close()

    def load(self, source: Optional[Union[str, Path]] = None) -> int:
        """Loads chunks and vectors from SQLite."""
        load_path = Path(source) if source else self.db_path
        if not load_path or not load_path.exists():
            return 0

        conn = sqlite3.connect(load_path)
        cursor = conn.cursor()
        cursor.execute("SELECT chunk_id, doc_id, chunk_index, content, token_count, metadata_json, embedding_json FROM chunks")
        rows = cursor.fetchall()
        conn.close()

        loaded_chunks: List[Chunk] = []
        for row in rows:
            c_id, doc_id, idx, content, tokens, meta_json, emb_json = row
            metadata = json.loads(meta_json) if meta_json else {}
            embedding = json.loads(emb_json) if emb_json else None
            chunk = Chunk(
                content=content,
                doc_id=doc_id,
                chunk_index=idx,
                chunk_id=c_id,
                token_count=tokens,
                metadata=metadata,
                embedding=embedding,
            )
            loaded_chunks.append(chunk)

        self.chunks = loaded_chunks
        self._bm25_stale = True
        return len(loaded_chunks)

    def stats(self) -> Dict[str, Any]:
        """Returns summary statistics for the stored vectors."""
        unique_docs = len({c.doc_id for c in self.chunks})
        total_tokens = sum(c.token_count for c in self.chunks)
        dim = self.embedder.dimension

        return {
            "total_chunks": len(self.chunks),
            "unique_documents": unique_docs,
            "total_tokens": total_tokens,
            "embedding_dimension": dim,
            "has_persistence": bool(self.db_path),
            "db_path": str(self.db_path) if self.db_path else None,
        }
