import json
from pathlib import Path
from functools import lru_cache
from typing import Dict, Any, Optional


CONTRACTS_BASE_DIR = Path("data/contracts")


# Cache loaded metadata to avoid repeated file reads
@lru_cache(maxsize=1024)
def load_contract_html_metadata(contract_id: str) -> Optional[Dict[str, Any]]:
    """
    Load HTML metadata JSON for a given contract.

    Assumes structure:
      data/contracts/<contract_id>/html_metadata_json/*.json

    If multiple files exist, it loads the first one.
    """
    meta_dir = CONTRACTS_BASE_DIR / contract_id / "html_metadata_json"
    if not meta_dir.exists() or not meta_dir.is_dir():
        return None

    json_files = sorted(meta_dir.glob("*.json"))
    if not json_files:
        return None

    path = json_files[0]
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None