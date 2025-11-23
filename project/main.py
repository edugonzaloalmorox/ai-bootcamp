

from pathlib import Path
import time
import logging
import json

from src.contracts.models import ContractRecord
from src.scraper import paginate_contract_links
from src.scraper.detail import process_contract_detail
from src.knowledge_base.prepare_kb import prepare_kb_corpus
from src.knowledge_base.vector_base_config import get_qdrant_client

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

# -------------------------------------------------------------------
# Logging configuration
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

log = logging.getLogger("main")

SEARCH_URL = "https://contratos-publicos.comunidad.madrid/contratos"

# Expected embedding dimension for the model in use
EMBED_DIM = 1536  # text-embedding-3-small → 1536 dims
QDRANT_COLLECTION = "pliegos_kb_sample"


# -------------------------------------------------------------------
# Select a small subset of contracts (first N) for vectorization
# -------------------------------------------------------------------
def select_first_contracts(kb_jsonl_path: Path, n: int = 3) -> set[str]:
    """
    Read the prepared KB JSONL file and return the first `n` unique
    contract IDs found. This allows us to vectorize a small sample
    instead of the full corpus.
    """
    contract_ids: list[str] = []

    with kb_jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            if len(contract_ids) >= n:
                break
            rec = json.loads(line)
            cid = rec["payload"]["contract_id"]
            if cid not in contract_ids:
                contract_ids.append(cid)

    log.info("[KB] Selected contracts for vectorization: %s", contract_ids)
    return set(contract_ids)


# -------------------------------------------------------------------
# Embedding function (OpenAI)
# -------------------------------------------------------------------
_first_embedding_logged = False


def embed_text(text: str) -> list[float]:
    """
    Compute an OpenAI embedding for the given text.

    IMPORTANT:
    If you change the embedding model, update `EMBED_DIM` accordingly.
    """
    global _first_embedding_logged
    from openai import OpenAI

    client = OpenAI()

    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    vec = resp.data[0].embedding

    # Log the dimension only once
    if not _first_embedding_logged:
        _first_embedding_logged = True
        log.info("[EMB] First embedding generated (dim=%d)", len(vec))

    if len(vec) != EMBED_DIM:
        raise ValueError(
            f"Embedding dimension {len(vec)} != expected {EMBED_DIM}. "
            "Update EMBED_DIM or use a matching embedding model."
        )

    return vec


# -------------------------------------------------------------------
# Vectorize selected KB chunks and upsert them into Qdrant
# -------------------------------------------------------------------
def vectorize_sample_kb(
    kb_jsonl_path: Path,
    selected_ids: set[str],
    client: QdrantClient,
) -> None:
    """
    Vectorize only the KB chunks belonging to the selected contract IDs
    and upsert them into a dedicated Qdrant collection.
    """
    log.info(
        "[QDRANT] Creating collection '%s' with dim=%d",
        QDRANT_COLLECTION,
        EMBED_DIM,
    )

    client.recreate_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=qm.VectorParams(
            size=EMBED_DIM,
            distance=qm.Distance.COSINE,
        ),
    )

    points_batch: list[qm.PointStruct] = []
    batch_size = 32
    total_points = 0

    with kb_jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            payload = rec["payload"]
            cid = payload["contract_id"]

            # Only vectorize the selected contracts
            if cid not in selected_ids:
                continue

            vec = embed_text(rec["text"])

            points_batch.append(
                qm.PointStruct(
                    id=rec["id"],
                    vector=vec,
                    payload=payload,
                )
            )
            total_points += 1

            if len(points_batch) >= batch_size:
                log.info(
                    "[QDRANT] Upserting batch of %d points (total=%d)",
                    len(points_batch),
                    total_points,
                )
                client.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=points_batch,
                )
                points_batch = []

    # flush remaining points
    if points_batch:
        log.info(
            "[QDRANT] Upserting final batch of %d points (total=%d)",
            len(points_batch),
            total_points,
        )
        client.upsert(
            collection_name=QDRANT_COLLECTION,
            points=points_batch,
        )

    # Verification: count stored points
    count_resp = client.count(
        collection_name=QDRANT_COLLECTION,
        exact=True,
    )

    log.info(
        "[QDRANT] Stored points in collection '%s': %d",
        QDRANT_COLLECTION,
        count_resp.count,
    )

    if count_resp.count != total_points:
        log.warning(
            "[QDRANT] WARNING: mismatch (uploaded=%d, stored=%d)",
            total_points,
            count_resp.count,
        )
    else:
        log.info("[OK] Embedding + vectorization + upsert completed successfully.")


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
def main() -> None:
    """
    Full pipeline:

    1. Scrape a small number of contract detail pages.
    2. Generate a KB corpus (non-vectorized) from `embeddings_corpus.jsonl`.
    3. Select three sample contracts.
    4. Embed and store them in Qdrant for retrieval experiments.
    """
    client = get_qdrant_client()
    log.info("[QDRANT] Client initialized.")

    # --- 1) Scraping (kept for continuity with your workflow) ---
    urls = paginate_contract_links(SEARCH_URL, max_pages=2)
    selected = urls[:10]

    records: list[ContractRecord] = []

    for idx, url in enumerate(selected, 1):
        print(f"[{idx}/{len(selected)}] {url}")
        record = process_contract_detail(url)
        records.append(record)
        time.sleep(1)

    print("Processed:", len(records))

    # --- 2) Prepare KB corpus from embeddings_corpus.jsonl ---
    embeddings_corpus_path = Path("embeddings_corpus.jsonl")

    if not embeddings_corpus_path.exists():
        print("ERROR: embeddings_corpus.jsonl not found")
        return

    kb_chunks_path = Path("data/kb/kb_chunks.jsonl")

    prepare_kb_corpus(
        embeddings_corpus_path=embeddings_corpus_path,
        output_jsonl_path=kb_chunks_path,
    )

    print(f"KB chunks generated: {kb_chunks_path}")

    # --- 3) Select only 3 contracts for vectorization ---
    selected_ids = select_first_contracts(kb_chunks_path, n=3)

    # --- 4) Vectorize + upsert into Qdrant ---
    vectorize_sample_kb(
        kb_jsonl_path=kb_chunks_path,
        selected_ids=selected_ids,
        client=client,
    )


if __name__ == "__main__":
    main()
