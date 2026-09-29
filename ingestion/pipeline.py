"""End-to-end Ingestion and Processing Pipeline orchestrator."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ingestion.chunker import BaseChunker, RecursiveCharacterChunker
from ingestion.loader import BaseLoader, DirectoryLoader, TextLoader
from ingestion.models import Chunk, Document, IngestionReport, SearchResult
from ingestion.preprocessor import TextPreprocessor
from ingestion.vector_store import VectorStore


class IngestionPipeline:
    """
    Unified pipeline orchestrating:
      Data Source -> Document Loading -> Text Preprocessing -> Chunking -> Vector Indexing -> Semantic Search
    """

    def __init__(
        self,
        loader: Optional[BaseLoader] = None,
        preprocessor: Optional[TextPreprocessor] = None,
        chunker: Optional[BaseChunker] = None,
        vector_store: Optional[VectorStore] = None,
        db_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.loader = loader or DirectoryLoader()
        self.preprocessor = preprocessor or TextPreprocessor()
        self.chunker = chunker or RecursiveCharacterChunker(chunk_size=500, chunk_overlap=50)
        self.vector_store = vector_store or VectorStore(db_path=db_path)

    def run(self, source: Union[str, Path]) -> IngestionReport:
        """Runs the complete ingestion and indexing cycle on a file or directory."""
        start_time = time.time()
        report = IngestionReport()
        path = Path(source)

        if not path.exists():
            report.errors.append(f"Source path does not exist: {path}")
            report.duration_seconds = time.time() - start_time
            return report

        try:
            # 1. Loading
            if path.is_dir():
                raw_docs = self.loader.load(path)
            else:
                ext = path.suffix.lower()
                specific_loader = DirectoryLoader.DEFAULT_EXTENSIONS.get(ext, TextLoader)()
                raw_docs = specific_loader.load(path)

            report.documents_loaded = len(raw_docs)

            # 2. Preprocessing & Normalization
            clean_docs: List[Document] = []
            for doc in raw_docs:
                cleaned_content = self.preprocessor.clean(doc.content)
                if cleaned_content:
                    doc.content = cleaned_content
                    clean_docs.append(doc)

            # 3. Chunking
            chunks: List[Chunk] = self.chunker.split_documents(clean_docs)
            report.chunks_created = len(chunks)
            report.total_tokens = sum(c.token_count for c in chunks)

            # 4. Embedding & Indexing
            self.vector_store.add_chunks(chunks)

        except Exception as exc:
            report.errors.append(str(exc))

        report.duration_seconds = time.time() - start_time
        return report

    def query(
        self,
        text: str,
        top_k: int = 5,
        hybrid: bool = True,
        alpha: float = 0.7,
    ) -> List[SearchResult]:
        """Queries the vector store for semantic or hybrid matches."""
        return self.vector_store.search(
            query=text,
            top_k=top_k,
            hybrid=hybrid,
            alpha=alpha,
        )

    def stats(self) -> Dict[str, Any]:
        """Returns statistics on the current index."""
        return self.vector_store.stats()
