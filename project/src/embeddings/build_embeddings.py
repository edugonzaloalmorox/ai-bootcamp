import json
from pathlib import Path
from typing import NoReturn

from src.embeddings.corpus_builder import iter_embedding_records


# Output corpus file
OUTPUT_PATH = Path("embeddings_corpus.jsonl")

# Location of contract directories (each contract contains its extracted text)
CONTRACTS_DIR = Path("data/contracts")


def main() -> NoReturn:
    """
    Generate an embeddings corpus file from processed contract documents.

    This script:
      1. Validates that the contract directory exists.
      2. Iterates through all embedding records produced by `iter_embedding_records`.
      3. Writes each record as a JSONL line to `embeddings_corpus.jsonl`.
      4. Reports the total number of records generated and warns if zero.

    The output format is compatible with vector database ingestion
    """
    # Validate contract directory
    if not CONTRACTS_DIR.exists():
        print(f"⚠️ Contract directory not found: {CONTRACTS_DIR.resolve()}")
        print("   Ensure you are running this script from the project root, and that")
        print("   'data/contracts/' contains the extracted contract files.")
        return

    total_records = 0

    # Generate JSONL corpus
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for rec in iter_embedding_records(CONTRACTS_DIR):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total_records += 1

    print(f"✅ Done. Wrote {total_records} embedding records to: {OUTPUT_PATH.resolve()}")

    if total_records == 0:
        print("⚠️ No records were generated. Possible reasons:")
        print("   - data/contracts/ is empty")
        print("   - Missing pliego_admin_text.json / pliego_tecnico_text.json")
        print("   - Unexpected JSON structure inside those files")
        print("   - The extractor did not produce any text segments")


if __name__ == "__main__":
    main()
