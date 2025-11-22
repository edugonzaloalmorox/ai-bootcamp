import json
import logging
from pathlib import Path
from typing import Dict

from src.scraper.config import DATA_ROOT
from src.scraper.files import safe_filename
from .models import ContractRecord
from src.extractor.pdf_text_extractor import PdfText

logger = logging.getLogger(__name__)

DATA_ROOT_PATH = Path(DATA_ROOT)


def get_contract_dir(contract_id: str) -> Path:
    """
    Ensure and return the directory for a given contract_id under DATA_ROOT.
    """
    cid = safe_filename(contract_id)
    contract_dir = DATA_ROOT_PATH / cid
    contract_dir.mkdir(parents=True, exist_ok=True)
    return contract_dir


def save_metadata(record: ContractRecord) -> Path:
    """
    Save raw HTML metadata to:
      data/contracts/<contract_id>/html_metadata.json
    """
    contract_dir = get_contract_dir(record.contract_id)
    metadata_path = contract_dir / "html_metadata.json"

    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(record.metadata_raw.data, f, ensure_ascii=False, indent=2)

    logger.info("[STORE] RAW metadata saved to %s", metadata_path)
    return metadata_path


def save_pdf_texts(contract_id: str, pdf_texts: Dict[str, PdfText]) -> Dict[str, Path]:
    """
    Save extracted text for each PDF associated with a contract.

    For each key (e.g. 'pliego_admin'), this writes a JSON file:
      data/contracts/<contract_id>/<key>_text.json

    JSON structure:
      {
        "source": "...",
        "num_pages": N,
        "pages": [
          {"page_number": 0, "text": "..."},
          ...
        ]
      }
    """
    contract_dir = get_contract_dir(contract_id)
    result_paths: Dict[str, Path] = {}

    for key, pdf_text in pdf_texts.items():
        out_path = contract_dir / f"{key}_text.json"
        payload = {
            "source": pdf_text.source,
            "num_pages": pdf_text.num_pages,
            "pages": [
                {"page_number": p.page_number, "text": p.text}
                for p in pdf_text.pages
            ],
        }
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        logger.info("[STORE] PDF text for %s saved to %s", key, out_path)
        result_paths[key] = out_path

    return result_paths


def verify_pdfs(record: ContractRecord) -> Dict[str, bool]:
    """
    Check that the PDF paths stored in record.pdfs exist on disk.
    """
    statuses: Dict[str, bool] = {}
    for key, path_str in record.pdfs.items():
        path = Path(path_str)
        exists = path.is_file()
        statuses[key] = exists
        if not exists:
            logger.warning("Expected PDF not found: %s → %s", key, path)
    return statuses


def save_contract_record(record: ContractRecord) -> None:
    """
    Storage entrypoint:

    - ensure contract directory
    - save raw metadata
    - verify that PDFs exist
    - (future) update a global index or additional artifacts
    """
    _ = get_contract_dir(record.contract_id)
    save_metadata(record)
    verify_pdfs(record)
