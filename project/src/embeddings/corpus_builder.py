from pathlib import Path
import json
from typing import Dict, Any, Iterable, List

from src.embeddings.chunking import chunk_page_text, ChunkingConfig

# Default path where processed contract folders are stored
BASE_CONTRACTS_DIR = Path("data/contracts")


def load_json(path: Path) -> Any:
    """
    Load JSON content from a file path.

    Parameters
    ----------
    path : Path
        The path to the JSON file.

    Returns
    -------
    Any
        Parsed JSON content.
    """
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_embedding_records(
    base_dir: Path = BASE_CONTRACTS_DIR,
) -> Iterable[Dict[str, Any]]:
    """
    Iterate over all processed contracts and yield embedding-ready records.

    Each yielded record has the structure:

    {
        "id": str,
        "text": str,
        "metadata": dict
    }

    These records can be directly fed into an embedding model, then stored
    in a vector database (e.g., Qdrant, pgvector, Weaviate, Chroma).

    Parameters
    ----------
    base_dir : Path, optional
        Directory that contains subfolders, each representing one contract.

    Yields
    ------
    Dict[str, Any]
        A dictionary with chunk text, ID, and metadata fields.
    """
    # Chunking configuration for all documents
    chunk_config = ChunkingConfig(
        max_chars=1500,
        min_chars=400,
        overlap_segments=1,
    )

    # Iterate through contract directories
    for contract_dir in base_dir.iterdir():
        if not contract_dir.is_dir():
            continue

        contract_id = contract_dir.name

        # ------------------------------------------------------------------
        # 1) Load HTML metadata if present — used to enrich all chunk metadata
        # ------------------------------------------------------------------
        html_meta_path = contract_dir / "html_metadata.json"
        html_meta: Dict[str, Any] = {}

        if html_meta_path.exists():
            try:
                html_meta = load_json(html_meta_path)
            except Exception:
                # If the file is corrupt or malformed, ignore metadata gracefully
                html_meta = {}

        # ------------------------------------------------------------------
        # 2) Process textual documents to be embedded
        # ------------------------------------------------------------------
        for filename, document_type, scope in [
            ("pliego_admin_text.json", "pliego_admin", "admin"),
            ("pliego_tecnico_text.json", "pliego_tecnico", "tecnico"),
        ]:
            doc_path = contract_dir / filename
            if not doc_path.exists():
                continue

            doc_data = load_json(doc_path)

            # Support two shapes:
            #  - List of pages: [{"page": 1, "text": "..."}]
            #  - Raw full text in a single string
            if isinstance(doc_data, list):
                pages_iter = doc_data
            else:
                pages_iter = [{"page": None, "text": str(doc_data)}]

            # --------------------------------------------------------------
            # Iterate over pages and chunk each one using the chunking strategy
            # --------------------------------------------------------------
            for page_obj in pages_iter:
                page = page_obj.get("page")
                text = page_obj.get("text", "")

                if not text or not text.strip():
                    continue

                # Apply chunking strategy
                chunks = chunk_page_text(text, config=chunk_config)

                # ----------------------------------------------------------
                # Yield one record per chunk
                # ----------------------------------------------------------
                for chunk_idx, chunk_text in enumerate(chunks):
                    record_id_parts = [contract_id, document_type]

                    if page is not None:
                        record_id_parts.append(f"p{int(page):03d}")

                    record_id_parts.append(f"c{chunk_idx:03d}")
                    record_id = "::".join(record_id_parts)

                    metadata = {
                        "contract_id": contract_id,
                        "document_type": document_type,
                        "page": page,
                        "chunk_index": chunk_idx,
                        "source_file": filename,
                        "search_scope": scope,
                        # Prefix HTML metadata to avoid collisions
                        **{f"meta_{k}": v for k, v in html_meta.items()},
                    }

                    yield {
                        "id": record_id,
                        "text": chunk_text,
                        "metadata": metadata,
                    }
