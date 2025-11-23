import json
from pathlib import Path
from typing import Iterable, Dict, Any

from .chunking_adapter import iter_page_chunks_for_kb


def prepare_kb_corpus(
    embeddings_corpus_path: Path,
    output_jsonl_path: Path,
) -> None:
    """
    Lee embeddings_corpus.jsonl → parsea → chunking → payload metadata
    y genera un jsonl listo para vectorizar y subir a Qdrant.

    NO vectoriza todavía.
    """
    output_jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    with output_jsonl_path.open("w", encoding="utf-8") as out:
        for chunk in iter_page_chunks_for_kb(embeddings_corpus_path):
            out.write(json.dumps({
                "id": chunk.id,
                "text": chunk.text,
                "payload": chunk.metadata,
            }, ensure_ascii=False))
            out.write("\n")

    print(f"[KB] Corpus preparado: {output_jsonl_path}")