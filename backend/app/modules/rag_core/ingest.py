"""
app/modules/rag_core/ingest.py
PDF ingestion pipeline: extraction, chunking, embedding, and FAISS category indexes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import faiss
import numpy as np
import pypdf

from app.core.config import settings

# ── Chunking Constants ────────────────────────────────────────────────────────
CHUNK_TARGET_SIZE = 900
CHUNK_OVERLAP = 150
MIN_PAGE_CHARS_WARNING = 50


class Chunk:
    def __init__(
        self,
        chunk_id: str,
        text: str,
        source: str,
        page: int,
        category: str,
    ):
        self.chunk_id = chunk_id
        self.text = text
        self.source = source
        self.page = page
        self.category = category

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source": self.source,
            "page": self.page,
            "category": self.category,
        }


def compute_file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def split_text_into_chunks(
    text: str,
    target_size: int = CHUNK_TARGET_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """Split text into chunks of roughly target_size characters with overlap,
    prioritizing paragraph and sentence boundaries.
    """
    clean_text = text.replace("\r\n", "\n").strip()
    if not clean_text:
        return []

    if len(clean_text) <= target_size:
        return [clean_text]

    # Split by paragraphs
    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    raw_segments: List[str] = []

    for para in paragraphs:
        if len(para) <= target_size:
            raw_segments.append(para)
        else:
            # Split paragraph by sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for s in sentences:
                s_strip = s.strip()
                if not s_strip:
                    continue
                if len(s_strip) <= target_size:
                    raw_segments.append(s_strip)
                else:
                    # Fallback to word splitting
                    words = s_strip.split()
                    cur_w = ""
                    for w in words:
                        if len(cur_w) + len(w) + 1 <= target_size:
                            cur_w = f"{cur_w} {w}" if cur_w else w
                        else:
                            if cur_w:
                                raw_segments.append(cur_w)
                            cur_w = w
                    if cur_w:
                        raw_segments.append(cur_w)

    chunks: List[str] = []
    current_chunk = ""

    for seg in raw_segments:
        if not current_chunk:
            current_chunk = seg
        elif len(current_chunk) + len(seg) + 2 <= target_size:
            current_chunk = f"{current_chunk}\n\n{seg}"
        else:
            chunks.append(current_chunk)
            # Create overlap
            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
            current_chunk = f"{overlap_text}\n\n{seg}" if overlap_text else seg

    if current_chunk and (not chunks or chunks[-1] != current_chunk):
        chunks.append(current_chunk)

    return chunks


def extract_and_chunk_pdf(
    pdf_path: Path,
    category: str,
) -> Tuple[List[Chunk], int, int]:
    """Extract text from a PDF page by page and chunk it.
    Returns (chunks, total_pages, scanned_pages_count).
    """
    reader = pypdf.PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    scanned_pages_count = 0
    all_chunks: List[Chunk] = []

    file_slug = re.sub(r"[^a-zA-Z0-9]+", "_", pdf_path.stem).strip("_").lower()

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        page_text = page.extract_text() or ""
        cleaned = page_text.strip()

        if len(cleaned) < MIN_PAGE_CHARS_WARNING:
            scanned_pages_count += 1
            print(
                f"Warning: {pdf_path.name} page {page_num} has only {len(cleaned)} characters (may be scanned)"
            )

        if not cleaned:
            continue

        raw_chunks = split_text_into_chunks(cleaned)
        for c_idx, text_chunk in enumerate(raw_chunks):
            chunk_id = f"{category}_{file_slug}_p{page_num}_c{c_idx + 1}"
            all_chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    text=text_chunk,
                    source=pdf_path.name,
                    page=page_num,
                    category=category,
                )
            )

    return all_chunks, total_pages, scanned_pages_count


class SentenceTransformerEmbedder:
    """Wrapper around sentence-transformers with lazy loading."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        self._load()
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return np.asarray(embeddings, dtype=np.float32)


class FakeEmbedder:
    """Deterministic hash-based embedder for lightning-fast testing without downloads."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        vectors = []
        for text in texts:
            seed = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % (2**32)
            rng = np.random.default_rng(seed)
            vec = rng.standard_normal(self.dimension).astype(np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            vectors.append(vec)
        return np.vstack(vectors)


def build_category_index(
    chunks: List[Chunk],
    embedder: Any,
    category: str,
    vectorstore_dir: Path,
) -> None:
    """Embed chunks, build FAISS IndexFlatIP, and save index + metadata."""
    vectorstore_dir.mkdir(parents=True, exist_ok=True)
    index_path = vectorstore_dir / f"{category}.faiss"
    metadata_path = vectorstore_dir / f"{category}_chunks.json"

    if not chunks:
        dim = getattr(embedder, "dimension", 384)
        index = faiss.IndexFlatIP(dim)
        faiss.write_index(index, str(index_path))
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        return

    texts = [c.text for c in chunks]
    embeddings = embedder.embed_texts(texts)

    # Normalize L2 just in case
    faiss.normalize_L2(embeddings)

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    index_path = vectorstore_dir / f"{category}.faiss"
    faiss.write_index(index, str(index_path))

    metadata_path = vectorstore_dir / f"{category}_chunks.json"
    metadata = [c.to_dict() for c in chunks]
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def run_ingest(
    docs_dir: Optional[Path] = None,
    vectorstore_dir: Optional[Path] = None,
    rebuild: bool = False,
    embedder: Optional[Any] = None,
) -> Dict[str, Any]:
    """Execute ingestion pipeline with manifest enforcement and idempotent state."""
    d_dir = docs_dir or Path(settings.DOCS_DIR)
    v_dir = vectorstore_dir or Path(settings.VECTORSTORE_DIR)
    v_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = d_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file missing at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest: Dict[str, str] = json.load(f)

    # Validate that all PDFs in d_dir are mapped in the manifest
    pdf_files = list(d_dir.glob("*.pdf"))
    for pdf in pdf_files:
        if pdf.name not in manifest:
            raise ValueError(
                f"PDF '{pdf.name}' found in docs directory but missing from manifest.json"
            )

    # State file for idempotency
    state_file = v_dir / "state.json"
    current_state: Dict[str, Any] = {"files": {}}
    if state_file.exists() and not rebuild:
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                current_state = json.load(f)
        except Exception:
            current_state = {"files": {}}

    old_files_state = current_state.get("files", {})
    categories_to_rebuild: set[str] = set()

    file_hashes: Dict[str, str] = {}
    for pdf in pdf_files:
        file_hash = compute_file_sha256(pdf)
        file_hashes[pdf.name] = file_hash
        category = manifest[pdf.name]

        prev_hash = old_files_state.get(pdf.name, {}).get("sha256")
        if rebuild or prev_hash != file_hash:
            categories_to_rebuild.add(category)

    # Also check if index files exist on disk for each category
    all_categories = set(manifest.values())
    for cat in all_categories:
        if not (v_dir / f"{cat}.faiss").exists() or not (v_dir / f"{cat}_chunks.json").exists():
            categories_to_rebuild.add(cat)

    if not categories_to_rebuild:
        print("All documents are up-to-date and indexes exist. Skipping ingestion.")
        return {
            "files_processed": 0,
            "categories_rebuilt": [],
            "chunks_per_category": {},
            "warnings_count": 0,
        }

    # Instantiate embedder if not provided
    if embedder is None:
        embedder = SentenceTransformerEmbedder(model_name=settings.EMBEDDING_MODEL)

    category_chunks: Dict[str, List[Chunk]] = {c: [] for c in all_categories}
    total_pages = 0
    total_scanned_warnings = 0
    files_processed = 0

    for pdf in pdf_files:
        cat = manifest[pdf.name]
        if cat in categories_to_rebuild:
            chunks, pages, scanned_count = extract_and_chunk_pdf(pdf, cat)
            category_chunks[cat].extend(chunks)
            total_pages += pages
            total_scanned_warnings += scanned_count
            files_processed += 1

    chunks_per_cat: Dict[str, int] = {}
    for cat in categories_to_rebuild:
        chunks = category_chunks.get(cat, [])
        chunks_per_cat[cat] = len(chunks)
        build_category_index(chunks, embedder, cat, v_dir)
        print(f"Built FAISS index for '{cat}' with {len(chunks)} chunks.")

    # Update state file
    new_files_state = {}
    for pdf in pdf_files:
        new_files_state[pdf.name] = {
            "sha256": file_hashes[pdf.name],
            "category": manifest[pdf.name],
        }
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"files": new_files_state}, f, indent=2)

    result_summary = {
        "files_processed": files_processed,
        "total_pages": total_pages,
        "categories_rebuilt": list(categories_to_rebuild),
        "chunks_per_category": chunks_per_cat,
        "warnings_count": total_scanned_warnings,
    }
    print(
        f"Ingestion complete: {files_processed} files processed, {total_pages} pages, "
        f"{chunks_per_cat} chunks, {total_scanned_warnings} warnings."
    )
    return result_summary


def main():
    parser = argparse.ArgumentParser(description="Ingest PDFs into category-specific FAISS indexes.")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild all category indexes.")
    args = parser.parse_args()

    run_ingest(rebuild=args.rebuild)


if __name__ == "__main__":
    main()
