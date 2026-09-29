"""Unit and integration tests for the ingestion and processing pipeline."""

import json
import tempfile
from pathlib import Path
import unittest

from ingestion.chunker import (
    MarkdownHeaderChunker,
    RecursiveCharacterChunker,
    estimate_tokens,
)
from ingestion.embeddings import (
    BM25Scorer,
    LocalDenseEmbedder,
    cosine_similarity,
)
from ingestion.loader import (
    CSVLoader,
    DirectoryLoader,
    JSONLoader,
    MarkdownLoader,
    TextLoader,
)
from ingestion.models import Chunk, Document
from ingestion.pipeline import IngestionPipeline
from ingestion.preprocessor import TextPreprocessor
from ingestion.vector_store import VectorStore


class TestTextPreprocessor(unittest.TestCase):
    def setUp(self):
        self.preprocessor = TextPreprocessor()

    def test_unicode_and_whitespace(self):
        raw = "Hello   world \u200b!\r\n\r\n\r\n\r\nSecond line.   "
        cleaned = self.preprocessor.clean(raw)
        self.assertIn("Hello world !", cleaned)
        self.assertIn("Second line.", cleaned)
        self.assertNotIn("\r", cleaned)
        # Should not have more than 2 consecutive newlines
        self.assertNotIn("\n\n\n", cleaned)


class TestLoaders(unittest.TestCase):
    def test_text_and_markdown_loader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p_txt = Path(tmpdir) / "sample.txt"
            p_txt.write_text("Plain text content here.", encoding="utf-8")

            txt_loader = TextLoader()
            docs = txt_loader.load(p_txt)
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0].content, "Plain text content here.")
            self.assertEqual(docs[0].metadata["filename"], "sample.txt")

            p_md = Path(tmpdir) / "post.md"
            p_md.write_text("---\ntitle: Guide\nauthor: Antigravity\n---\n# Header\nMarkdown body.", encoding="utf-8")
            md_loader = MarkdownLoader()
            md_docs = md_loader.load(p_md)
            self.assertEqual(len(md_docs), 1)
            self.assertIn("Markdown body.", md_docs[0].content)
            self.assertEqual(md_docs[0].metadata.get("fm_title"), "Guide")
            self.assertEqual(md_docs[0].metadata.get("fm_author"), "Antigravity")

    def test_json_and_csv_loader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p_json = Path(tmpdir) / "data.json"
            p_json.write_text(json.dumps([{"id": 1, "text": "Record 1"}, {"id": 2, "text": "Record 2"}]))
            json_loader = JSONLoader(text_key="text")
            j_docs = json_loader.load(p_json)
            self.assertEqual(len(j_docs), 2)
            self.assertEqual(j_docs[0].content, "Record 1")

            p_csv = Path(tmpdir) / "data.csv"
            p_csv.write_text("name,role\nAlice,Engineer\nBob,Architect")
            csv_loader = CSVLoader()
            c_docs = csv_loader.load(p_csv)
            self.assertEqual(len(c_docs), 2)
            self.assertIn("Engineer", c_docs[0].content)

    def test_excel_loader(self):
        excel_path = Path("Documents/dashboard .xlsx")
        if excel_path.exists():
            from ingestion.loader import ExcelLoader
            loader = ExcelLoader(include_summaries=True)
            docs = loader.load(excel_path)
            self.assertGreater(len(docs), 2900)
            # The first document should be the summary document
            self.assertTrue(docs[0].metadata.get("is_summary"))
            self.assertIn("Resumen Analítico", docs[0].content)


class TestChunkers(unittest.TestCase):
    def test_recursive_chunker(self):
        chunker = RecursiveCharacterChunker(chunk_size=60, chunk_overlap=15)
        text = "Paragraph one with several words.\n\nParagraph two with another sentence that keeps going on."
        doc = Document(content=text, metadata={"source": "test"})
        chunks = chunker.split_document(doc)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c.content), 80)
            self.assertGreater(c.token_count, 0)
            self.assertEqual(c.doc_id, doc.doc_id)

    def test_markdown_header_chunker(self):
        chunker = MarkdownHeaderChunker(max_chunk_size=200)
        md = "# Section 1\nContent of section 1.\n\n## Section 2\nContent of section 2."
        doc = Document(content=md, metadata={"source": "test.md"})
        chunks = chunker.split_document(doc)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].metadata.get("section_header"), "Section 1")
        self.assertEqual(chunks[1].metadata.get("section_header"), "Section 2")


class TestEmbeddingsAndVectorStore(unittest.TestCase):
    def test_local_embedder_and_cosine(self):
        embedder = LocalDenseEmbedder(dimension=128)
        v1 = embedder.embed_text("Machine learning and artificial intelligence")
        v2 = embedder.embed_text("Deep neural networks and artificial intelligence")
        v3 = embedder.embed_text("Baking chocolate cookies and cakes in the oven")

        self.assertEqual(len(v1), 128)
        sim_ai = cosine_similarity(v1, v2)
        sim_diff = cosine_similarity(v1, v3)
        self.assertGreater(sim_ai, sim_diff)

    def test_vector_store_persistence_and_hybrid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_store.db"
            store = VectorStore(embedder=LocalDenseEmbedder(dimension=64), db_path=db_path)

            chunks = [
                Chunk(content="Amazon Bedrock provides foundation models and knowledge bases.", doc_id="d1", chunk_index=0),
                Chunk(content="Local LLMs can be compiled using llama.cpp and quantized GGUF.", doc_id="d2", chunk_index=0),
                Chunk(content="Baking recipes for homemade sourdough bread.", doc_id="d3", chunk_index=0),
            ]
            store.add_chunks(chunks)
            self.assertEqual(len(store.chunks), 3)

            # Test query
            res = store.search("foundation models in Bedrock", top_k=1, hybrid=True)
            self.assertEqual(len(res), 1)
            self.assertIn("Bedrock", res[0].chunk.content)

            # Test reload from SQLite
            store_reloaded = VectorStore(embedder=LocalDenseEmbedder(dimension=64), db_path=db_path)
            self.assertEqual(len(store_reloaded.chunks), 3)
            stats = store_reloaded.stats()
            self.assertEqual(stats["total_chunks"], 3)


class TestIngestionPipeline(unittest.TestCase):
    def test_pipeline_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            (docs_dir / "doc1.txt").write_text("Deterministic programming with LLMs requires AST validation and testing.")
            (docs_dir / "doc2.md").write_text("# Capstone 1\nRAG architecture on AWS Bedrock.")

            db_file = Path(tmpdir) / "pipeline.db"
            pipeline = IngestionPipeline(db_path=db_file)
            report = pipeline.run(docs_dir)

            self.assertEqual(report.documents_loaded, 2)
            self.assertGreaterEqual(report.chunks_created, 2)
            self.assertEqual(len(report.errors), 0)

            # Query
            query_res = pipeline.query("AST validation and testing", top_k=1)
            self.assertEqual(len(query_res), 1)
            self.assertIn("Deterministic", query_res[0].chunk.content)


if __name__ == "__main__":
    unittest.main()
