
"""
ZentroMart Markdown Knowledge Base & Semantic Search Engine.

Features:
- Project-root relative paths for portability across working directories.
- Robust YAML frontmatter parsing for document metadata and versioning.
- Section-ID extraction directly from heading syntax (e.g. ## [RET-1] Scope).
- Comprehensive preservation of status, effective dates, versions, and supersession.
- Precedence ranking: Current Policy > Agent Guide > Help > FAQ > Marketing.
- Date-aware and historical policy retrieval for superseded documents (e.g. RETv3-2).
- FAISS cosine similarity index synchronized with chunks metadata.
- Numeric validation, finite embedding checks, atomic writes, and deduplication.
"""

from pathlib import Path
import json
import re
import argparse

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# Resolve project root portably from this file's location
PROJECT_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = PROJECT_ROOT / "dataset" / "kb"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INDEX_PATH = ARTIFACTS_DIR / "kb.faiss"
CHUNKS_PATH = ARTIFACTS_DIR / "chunks.json"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EXPECTED_EMBEDDING_DIM = 384

# Document category precedence defined in capstone brief & KB-00.1:
# 1. Policy (status: current)
# 2. Agent guides
# 3. Help articles
# 4. FAQs
# 5. Marketing pages
DOC_TYPE_PRIORITY = {
    "policy": 0,
    "agent_guide": 1,
    "agent": 1,
    "help": 2,
    "faq": 3,
    "marketing": 4,
    "meta": 5,
    "other": 5,
}

# Load the embedding model once.
model = SentenceTransformer(MODEL_NAME)

# In-memory cache for loaded index and chunk metadata
_cached_index = None
_cached_documents = None


# --------------------------------------------------
# 1. METADATA & DOCUMENT PARSING
# --------------------------------------------------

def parse_frontmatter(text):
    """
    Parse YAML frontmatter enclosed in leading '---' markers.
    Returns a dictionary of document metadata and the remaining Markdown body.
    """
    metadata = {
        "doc_id": None,
        "title": None,
        "doc_type": None,
        "audience": None,
        "language": None,
        "version": None,
        "effective_from": None,
        "status": "current",
        "supersedes": None,
        "superseded_by": None,
    }
    body = text

    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", text, re.DOTALL)
    if match:
        fm_content = match.group(1)
        body = match.group(2)
        for line in fm_content.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key in metadata:
                    metadata[key] = val

    return metadata, body


def get_doc_type(metadata, filename):
    """Identify document category from frontmatter or filename prefix."""
    if metadata.get("doc_type"):
        return metadata["doc_type"]

    name = filename.lower()
    if name.startswith("pol_"):
        return "policy"
    if name.startswith("agent_"):
        return "agent_guide"
    if name.startswith("help_"):
        return "help"
    if name.startswith("faq_"):
        return "faq"
    if name.startswith("mkt_"):
        return "marketing"

    return "other"


def extract_section_id(heading_stack):
    """
    Extract section ID from current heading or nearest ancestor heading.
    Matches headings formatted like '## [RET-1] Scope' or '[KB-00.1]'.
    """
    for heading in reversed(heading_stack):
        match = re.match(r"^\[([A-Za-z0-9_\-\.]+)\](?:\s+.*)?$", heading.strip())
        if match:
            return match.group(1).strip()
    return None


def split_long_text(text, max_words=300, overlap=50):
    """Split long sections into overlapping word chunks."""
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap

    return chunks


def split_markdown(text):
    """
    Split Markdown using headings.
    Extracts document-level title and preamble (content before first ## heading),
    and creates chunks for each section with its section_id and contextual hierarchy.
    """
    sections = []
    lines = text.splitlines()
    preamble_lines = []
    body_start_idx = 0
    doc_title = None

    for idx, line in enumerate(lines):
        h1_match = re.match(r"^\s{0,3}#\s+(.+?)\s*#*\s*$", line)
        if h1_match and doc_title is None:
            doc_title = h1_match.group(1).strip()
            continue
        if re.match(r"^\s{0,3}##\s+", line):
            body_start_idx = idx
            break
        if doc_title is not None and line.strip():
            cleaned = re.sub(r"^\s*>\s*", "", line).strip()
            if cleaned:
                preamble_lines.append(cleaned)
    else:
        body_start_idx = len(lines)

    doc_preamble = " ".join(preamble_lines).strip()
    heading_stack = [doc_title] if doc_title else []
    current_lines = []

    def save_current():
        content = "\n".join(current_lines).strip()
        if not content:
            return

        heading_path = " > ".join(heading_stack)
        sec_id = extract_section_id(heading_stack)

        if doc_preamble:
            full_text = f"Heading: {heading_path}\nContext: {doc_preamble}\n\n{content}"
        else:
            full_text = f"Heading: {heading_path}\n{content}"

        for part_number, chunk in enumerate(
            split_long_text(full_text),
            start=1,
        ):
            sections.append({
                "heading_path": heading_path,
                "section_id": sec_id,
                "text": chunk,
                "part_number": part_number,
            })

    for line in lines[body_start_idx:]:
        match = re.match(
            r"^\s{0,3}(#{2,6})\s+(.+?)\s*#*\s*$",
            line,
        )
        if match:
            save_current()
            current_lines.clear()

            level = len(match.group(1))
            heading = match.group(2).strip()

            base_len = 1 if doc_title else 0
            heading_stack[:] = heading_stack[:base_len + level - 2]
            heading_stack.append(heading)

            current_lines.append(line)
        else:
            current_lines.append(line)

    save_current()
    return sections


# --------------------------------------------------
# 2. BUILD DOCUMENT CHUNKS
# --------------------------------------------------

def load_documents():
    """
    Read all Markdown files, extract YAML frontmatter and section IDs,
    and attach complete metadata to each chunk.
    """
    if not KB_DIR.exists() or not KB_DIR.is_dir():
        raise FileNotFoundError(
            f"Knowledge base folder not found at '{KB_DIR}'. "
            "Please ensure dataset/kb is present in the project root."
        )

    # First pass: load frontmatter and identify successor linkages
    file_records = []
    successor_map = {}  # superseded doc_id -> successor effective_from

    for file_path in sorted(KB_DIR.rglob("*.md")):
        # Only process intended Markdown files, ignoring hidden or temp files
        if file_path.name.startswith(".") or not file_path.is_file():
            continue

        raw_text = file_path.read_text(encoding="utf-8")
        if not raw_text.strip():
            continue

        metadata, body = parse_frontmatter(raw_text)
        doc_type = get_doc_type(metadata, file_path.name)
        file_records.append((file_path, metadata, doc_type, body))

        if metadata.get("supersedes"):
            successor_map[metadata["supersedes"]] = metadata.get("effective_from")

    documents = []

    for file_path, metadata, doc_type, body in file_records:
        rel_source = (
            str(file_path.relative_to(PROJECT_ROOT).as_posix())
            if file_path.is_relative_to(PROJECT_ROOT)
            else str(file_path)
        )

        # Derive effective_until for superseded policies
        effective_until = None
        if metadata.get("status") == "superseded":
            effective_until = successor_map.get(metadata.get("doc_id"))

        doc_priority = DOC_TYPE_PRIORITY.get(doc_type, 5)

        for section in split_markdown(body):
            documents.append({
                "source": rel_source,
                "doc_id": metadata.get("doc_id"),
                "doc_type": doc_type,
                "source_priority": doc_priority,
                "heading_path": section["heading_path"],
                "section_id": section["section_id"],
                "status": metadata.get("status", "current"),
                "effective_from": metadata.get("effective_from"),
                "effective_until": effective_until,
                "version": metadata.get("version"),
                "supersedes": metadata.get("supersedes"),
                "superseded_by": metadata.get("superseded_by"),
                "part_number": section["part_number"],
                "text": section["text"],
            })

    return documents


# --------------------------------------------------
# 3. EMBEDDING AND FAISS INDEXING
# --------------------------------------------------

def build_knowledge_base():
    """Embed document chunks, validate dimensions, and atomically save the FAISS index."""
    global _cached_index, _cached_documents

    documents = load_documents()
    if not documents:
        raise ValueError(f"No Markdown chunks found in {KB_DIR}")

    texts = [document["text"] for document in documents]

    print(f"Creating embeddings for {len(texts)} chunks across {len(set(d['source'] for d in documents))} files...")

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    # Validate embeddings
    if not isinstance(embeddings, np.ndarray) or not np.all(np.isfinite(embeddings)):
        raise ValueError("Generated embeddings contain non-finite or invalid numeric values (NaN/Inf).")

    if embeddings.ndim != 2:
        raise ValueError(f"Embeddings array has unexpected shape: {embeddings.shape}")

    if embeddings.shape[1] != EXPECTED_EMBEDDING_DIM:
        raise ValueError(
            f"Embedding dimension mismatch: expected {EXPECTED_EMBEDDING_DIM}, got {embeddings.shape[1]}"
        )

    embeddings = np.asarray(embeddings, dtype=np.float32)

    # Normalized vectors + inner product = cosine similarity.
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    if index.ntotal != len(documents):
        raise ValueError(
            f"FAISS index count ({index.ntotal}) does not match chunk count ({len(documents)})"
        )

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # Write atomically using temporary files to avoid partial/corrupt states
    temp_index_path = ARTIFACTS_DIR / "kb.faiss.tmp"
    temp_chunks_path = ARTIFACTS_DIR / "chunks.json.tmp"

    try:
        faiss.write_index(index, str(temp_index_path))
        temp_chunks_path.write_text(
            json.dumps(documents, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_index_path.replace(INDEX_PATH)
        temp_chunks_path.replace(CHUNKS_PATH)
    finally:
        if temp_index_path.exists():
            temp_index_path.unlink(missing_ok=True)
        if temp_chunks_path.exists():
            temp_chunks_path.unlink(missing_ok=True)

    # Invalidate cache
    _cached_index = None
    _cached_documents = None

    print(f"Indexed {len(documents)} chunks (dimension: {index.d}).")
    print(f"FAISS index saved to: {INDEX_PATH}")
    print(f"Chunk metadata saved to: {CHUNKS_PATH}")


# --------------------------------------------------
# 4. LOAD INDEX AND RETRIEVE RELEVANT CHUNKS
# --------------------------------------------------

def load_knowledge_base(force_reload=False):
    """
    Load the saved FAISS index and matching chunk metadata with validation.
    Caches in memory to avoid repeated disk reads.
    """
    global _cached_index, _cached_documents
    if not force_reload and _cached_index is not None and _cached_documents is not None:
        return _cached_index, _cached_documents

    missing = []
    if not INDEX_PATH.exists():
        missing.append(str(INDEX_PATH))
    if not CHUNKS_PATH.exists():
        missing.append(str(CHUNKS_PATH))

    if missing:
        raise FileNotFoundError(
            f"Knowledge base artifact(s) missing: {', '.join(missing)}. "
            f"Please build the index first using: python {Path(__file__).name} --build "
            f"(or from project root: python src/knowledge_base.py --build)"
        )

    try:
        index = faiss.read_index(str(INDEX_PATH))
    except Exception as exc:
        raise RuntimeError(f"Failed to read FAISS index at '{INDEX_PATH}': {exc}") from exc

    try:
        documents = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Failed to read chunk metadata at '{CHUNKS_PATH}': {exc}") from exc

    if not isinstance(documents, list):
        raise ValueError(
            f"Expected chunks metadata at '{CHUNKS_PATH}' to be a JSON list, got {type(documents).__name__}"
        )

    if index.ntotal != len(documents):
        raise ValueError(
            f"Index inconsistency: FAISS index has {index.ntotal} vectors, "
            f"but chunks.json has {len(documents)} entries. Please rebuild with --build."
        )

    if index.d != EXPECTED_EMBEDDING_DIM:
        raise ValueError(
            f"Index dimension mismatch: FAISS index vector dimension is {index.d}, "
            f"expected {EXPECTED_EMBEDDING_DIM} for model '{MODEL_NAME}'. Please rebuild with --build."
        )

    _cached_index = index
    _cached_documents = documents
    return _cached_index, _cached_documents


def retrieve(query, top_k=5, as_of_date=None):
    """
    Retrieve semantically similar chunks with precedence and version awareness.

    Parameters:
    - query (str): Customer inquiry or search terms.
    - top_k (int): Number of top results to return (must be > 0).
    - as_of_date (str, optional): Target ISO date (e.g. '2026-07-20'). If specified
      and prior to 2026-08-01, historical policy is prioritized over version 4.

    Returns:
    - List of chunk dicts including document metadata and 'similarity' score.
    """
    # Guard against invalid top_k or empty query
    if top_k is None or top_k <= 0:
        return []

    if query is None or not str(query).strip():
        return []

    clean_query = str(query).strip()

    index, documents = load_knowledge_base()
    if index.ntotal == 0 or len(documents) == 0:
        return []

    query_embedding = model.encode(
        [clean_query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype=np.float32,
    )

    if query_embedding.shape[1] != index.d:
        raise ValueError(
            f"Query embedding dimension ({query_embedding.shape[1]}) does not match "
            f"FAISS index dimension ({index.d})"
        )

    number_to_search = min(max(top_k * 4, 10), index.ntotal)

    scores, indices = index.search(
        query_embedding,
        number_to_search,
    )

    # Detect if query explicitly refers to historical policy dates
    is_historical_query = False
    if as_of_date:
        if str(as_of_date) < "2026-08-01":
            is_historical_query = True
    else:
        hist_pattern = r"\b(july|june|may|before\s+(?:1\s+)?august|earlier\s+policy|v3|version\s*3|superseded)\b"
        if re.search(hist_pattern, clean_query, flags=re.IGNORECASE):
            is_historical_query = True

    seen_indices = set()
    results = []

    for score, idx in zip(scores[0], indices[0]):
        idx_int = int(idx)
        if idx_int < 0 or idx_int >= len(documents):
            continue

        if idx_int in seen_indices:
            continue
        seen_indices.add(idx_int)

        result = documents[idx_int].copy()
        result["similarity"] = float(score)

        # Precedence adjustment:
        # Base penalty according to doc_type precedence (policy=0, agent=1, help=2, etc.)
        priority = result.get("source_priority", 5)

        # Status adjustment:
        # Current policy takes precedence over superseded policy for general queries.
        # If query is explicitly historical, superseded policy receives full weight.
        if result.get("status") == "superseded":
            if not is_historical_query:
                priority += 8  # Deprioritize superseded policies for modern queries

        result["_rank_score"] = result["similarity"] - (0.015 * priority)
        results.append(result)

    # Sort primarily by rank score
    results.sort(key=lambda item: item["_rank_score"], reverse=True)

    # Clean up internal rank score
    for item in results:
        item.pop("_rank_score", None)

    return results[:top_k]


# --------------------------------------------------
# 5. COMMAND-LINE INTERFACE
# --------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ZentroMart Markdown knowledge base"
    )

    parser.add_argument(
        "--build",
        action="store_true",
        help="Build and save the FAISS index",
    )

    parser.add_argument(
        "--query",
        type=str,
        help="Search the knowledge base",
    )

    parser.add_argument(
        "--date",
        type=str,
        help="Target as-of date (YYYY-MM-DD) for historical policy checks",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to retrieve (default: 5)",
    )

    args = parser.parse_args()

    if args.build:
        build_knowledge_base()

    elif args.query:
        results = retrieve(args.query, top_k=args.top_k, as_of_date=args.date)

        if not results:
            print("No matching chunks found.")
        else:
            for rank, result in enumerate(results, start=1):
                print(f"\n{'=' * 60}")
                print(f"Result {rank}")
                print(f"Source: {result['source']}")
                print(f"Section ID: {result.get('section_id')}")
                print(f"Section: {result['heading_path']}")
                print(f"Similarity: {result['similarity']:.4f}")
                print(f"Status: {result['status']}")
                print(f"Effective from: {result['effective_from']}")
                if result.get("effective_until"):
                    print(f"Effective until: {result['effective_until']}")
                print(f"\n{result['text']}")

    else:
        parser.print_help()

