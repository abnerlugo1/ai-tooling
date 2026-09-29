"""Document loaders for diverse file types and directories."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Union

from ingestion.models import Document


class BaseLoader:
    """Base interface for all document loaders."""

    def load(self, source: Union[str, Path]) -> List[Document]:
        """Loads and parses source into a list of Document objects."""
        raise NotImplementedError


class TextLoader(BaseLoader):
    """Loads plain text files."""

    def __init__(self, encoding: str = "utf-8") -> None:
        self.encoding = encoding

    def load(self, source: Union[str, Path]) -> List[Document]:
        path = Path(source)
        try:
            content = path.read_text(encoding=self.encoding)
        except UnicodeDecodeError:
            # Fallback with error replacement
            content = path.read_text(encoding=self.encoding, errors="replace")

        metadata: Dict[str, Any] = {
            "source": str(path.resolve()),
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
        }
        return [Document(content=content, metadata=metadata)]


class MarkdownLoader(BaseLoader):
    """Loads markdown files and extracts optional YAML-like frontmatter metadata."""

    def __init__(self, encoding: str = "utf-8") -> None:
        self.encoding = encoding

    def load(self, source: Union[str, Path]) -> List[Document]:
        path = Path(source)
        try:
            raw_content = path.read_text(encoding=self.encoding)
        except UnicodeDecodeError:
            raw_content = path.read_text(encoding=self.encoding, errors="replace")

        metadata: Dict[str, Any] = {
            "source": str(path.resolve()),
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
        }

        content = raw_content
        # Simple frontmatter parser without external dependencies
        if raw_content.startswith("---"):
            parts = raw_content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                content = parts[2].strip()
                for line in frontmatter_text.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        metadata[f"fm_{k.strip()}"] = v.strip().strip("\"'")

        return [Document(content=content, metadata=metadata)]


class JSONLoader(BaseLoader):
    """Loads JSON or JSONL files containing structured records."""

    def __init__(self, text_key: Optional[str] = None, encoding: str = "utf-8") -> None:
        self.text_key = text_key
        self.encoding = encoding

    def load(self, source: Union[str, Path]) -> List[Document]:
        path = Path(source)
        content_str = path.read_text(encoding=self.encoding, errors="replace")
        docs: List[Document] = []

        is_jsonl = path.suffix.lower() == ".jsonl"

        if is_jsonl:
            lines = [l.strip() for l in content_str.splitlines() if l.strip()]
            records = [json.loads(l) for l in lines]
        else:
            data = json.loads(content_str)
            records = data if isinstance(data, list) else [data]

        for idx, record in enumerate(records):
            if isinstance(record, dict):
                if self.text_key and self.text_key in record:
                    text = str(record[self.text_key])
                else:
                    # Concatenate all string fields or dump as formatted json string
                    text = json.dumps(record, ensure_ascii=False, indent=2)
                item_metadata = {
                    "source": str(path.resolve()),
                    "record_index": idx,
                    **{k: v for k, v in record.items() if not isinstance(v, (dict, list))},
                }
            else:
                text = str(record)
                item_metadata = {"source": str(path.resolve()), "record_index": idx}

            docs.append(Document(content=text, metadata=item_metadata))

        return docs


class CSVLoader(BaseLoader):
    """Loads tabular CSV records into individual or combined documents."""

    def __init__(self, content_columns: Optional[List[str]] = None, encoding: str = "utf-8") -> None:
        self.content_columns = content_columns
        self.encoding = encoding

    def load(self, source: Union[str, Path]) -> List[Document]:
        path = Path(source)
        docs: List[Document] = []

        with open(path, mode="r", encoding=self.encoding, errors="replace") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                if self.content_columns:
                    content_parts = [f"{col}: {row.get(col, '')}" for col in self.content_columns if col in row]
                    content = "\n".join(content_parts)
                else:
                    content = "\n".join(f"{k}: {v}" for k, v in row.items())

                metadata = {
                    "source": str(path.resolve()),
                    "row_index": idx,
                    "filename": path.name,
                }
                docs.append(Document(content=content, metadata=metadata))

        return docs


class DirectoryLoader(BaseLoader):
    """Scans and loads all matching documents in a directory recursively."""

    DEFAULT_EXTENSIONS = {
        ".txt": TextLoader,
        ".md": MarkdownLoader,
        ".markdown": MarkdownLoader,
        ".json": JSONLoader,
        ".jsonl": JSONLoader,
        ".csv": CSVLoader,
    }

    def __init__(
        self,
        extensions: Optional[List[str]] = None,
        recursive: bool = True,
        ignore_patterns: Optional[List[str]] = None,
    ) -> None:
        self.extensions = [ext.lower() for ext in extensions] if extensions else list(self.DEFAULT_EXTENSIONS.keys())
        self.recursive = recursive
        self.ignore_patterns = ignore_patterns or [".git", "node_modules", "__pycache__", ".venv"]

    def should_ignore(self, path: Path) -> bool:
        for pattern in self.ignore_patterns:
            if pattern in path.parts:
                return True
        return False

    def load(self, source: Union[str, Path]) -> List[Document]:
        base_path = Path(source)
        if not base_path.exists():
            raise FileNotFoundError(f"Directory not found: {base_path}")

        files: Generator[Path, None, None]
        if self.recursive:
            files = base_path.rglob("*")
        else:
            files = base_path.glob("*")

        documents: List[Document] = []

        for p in files:
            if p.is_file() and p.suffix.lower() in self.extensions:
                if self.should_ignore(p):
                    continue
                loader_cls = self.DEFAULT_EXTENSIONS.get(p.suffix.lower(), TextLoader)
                loader = loader_cls()
                try:
                    loaded = loader.load(p)
                    documents.extend(loaded)
                except Exception as e:
                    # Log or record error in document metadata if necessary
                    continue

        return documents
