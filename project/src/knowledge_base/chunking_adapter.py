from pathlib import Path
from typing import Iterable, Dict, Any, List

from src.embeddings.chunking import chunk_page_text, ChunkingConfig
from .corpus_loader import iter_pliego_page_texts, PageChunk
from .payload_loader import load_contract_html_metadata


# Default chunking configuration; adjust if needed
DEFAULT_CHUNK_CONFIG = ChunkingConfig(
    max_chars=1500,
    min_chars=400,
    overlap_segments=1,
)


def iter_page_chunks_for_kb(
    corpus_path: Path,
    chunk_config: ChunkingConfig = DEFAULT_CHUNK_CONFIG,
) -> Iterable[PageChunk]:
    """
    Iterate over pliego pages in the embeddings corpus and yield chunk-level
    records, ready to be embedded and stored in the vector database.

    This function:
      1. Reads per-page text from `embeddings_corpus.jsonl`.
      2. Loads HTML metadata for each contract from `data/contracts/<id>/html_metadata_json`.
      3. Splits each page into smaller text chunks using `chunk_page_text`.
      4. Builds `PageChunk` objects that carry both text and rich metadata.
    """
    for page in iter_pliego_page_texts(corpus_path):
        contract_id: str = page["contract_id"]
        doc_type: str = page["doc_type"]
        page_number: int = page["page_number"]
        page_text: str = page["text"]
        base_metadata: Dict[str, Any] = page["base_metadata"]

        # Load HTML metadata for this contract (cached)
        html_meta = load_contract_html_metadata(contract_id) or {}

        # NOTE: chunk_page_text does NOT accept `page_number` as a keyword argument.
        # We only pass the arguments it actually supports: text + config.
        text_chunks: List[str] = chunk_page_text(
            page_text,
            config=chunk_config,
        )

        for idx, chunk_text in enumerate(text_chunks):
            # Build the metadata payload for this specific chunk
            metadata: Dict[str, Any] = {
                **base_metadata,
                "page_number": page_number,
                "chunk_index": idx,
                # Normalized useful fields from HTML metadata (if present)
                "community": html_meta.get("community") or html_meta.get("autonomia"),
                "year": html_meta.get("year") or html_meta.get("anio"),
                "contract_title": html_meta.get("title") or html_meta.get("titulo"),
                # Full HTML metadata dump if you want richer filtering later
                "html_metadata": html_meta,
            }

            yield PageChunk(
                contract_id=contract_id,
                doc_type=doc_type,  # type: ignore[arg-type]
                page_number=page_number,
                chunk_index=idx,
                text=chunk_text,
                metadata=metadata,
            )