import json
from ast import literal_eval
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Iterable, Literal, List


DocType = Literal["pliego_admin", "pliego_tecnico"]


@dataclass
class PageChunk:
    contract_id: str
    doc_type: DocType
    page_number: int
    chunk_index: int
    text: str
    metadata: Dict[str, Any]

    @property
    def id(self) -> str:
        # Example: A-SUM-048553_2025::pliego_admin::p003::c001
        return (
            f"{self.contract_id}::"
            f"{self.doc_type}::"
            f"p{self.page_number:03d}::"
            f"c{self.chunk_index:03d}"
        )


def _parse_pliego_text_field(raw_text: str) -> Dict[str, Any]:
    """
    Parse the `text` field from embeddings_corpus.jsonl.

    The field is a stringified Python dict, not JSON, e.g.:

      "{'source': '...', 'num_pages': 51, 'pages': [...]}"

    We use ast.literal_eval to turn it into a dict safely.
    """
    return literal_eval(raw_text)


def iter_pliego_page_texts(
    corpus_path: Path,
) -> Iterable[Dict[str, Any]]:
    """
    Iterate over embeddings_corpus.jsonl and yield raw pages, without chunking.

    Yields dicts with:
      - contract_id
      - doc_type ('pliego_admin' | 'pliego_tecnico')
      - page_number
      - text
      - base_metadata (source, num_pages, etc.)
    """
    with corpus_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                # You may want to log this instead of silently skipping
                continue

            raw_id: str = record.get("id", "")
            parts = raw_id.split("::")
            if len(parts) < 2:
                continue

            contract_id = parts[0]
            doc_type = parts[1]

            if doc_type not in ("pliego_admin", "pliego_tecnico"):
                # Skip other doc types
                continue

            raw_text = record.get("text", "")
            if not raw_text:
                continue

            try:
                pliego_obj = _parse_pliego_text_field(raw_text)
            except Exception:
                # log and continue
                continue

            pages: List[Dict[str, Any]] = pliego_obj.get("pages", [])
            base_metadata: Dict[str, Any] = {
                "source_pdf": pliego_obj.get("source"),
                "num_pages": pliego_obj.get("num_pages"),
                "contract_id": contract_id,
                "doc_type": doc_type,
            }

            for page in pages:
                page_number = page.get("page_number")
                page_text = page.get("text", "")

                if page_number is None or not page_text.strip():
                    continue

                yield {
                    "contract_id": contract_id,
                    "doc_type": doc_type,
                    "page_number": int(page_number),
                    "text": page_text,
                    "base_metadata": base_metadata,
                }