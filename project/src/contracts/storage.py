import json
from pathlib import Path

from src.scraper.config import DATA_ROOT
from src.scraper.files import safe_filename
from .models import ContractRecord

DATA_ROOT_PATH = Path(DATA_ROOT)


def get_contract_dir(contract_id: str) -> Path:
    cid = safe_filename(contract_id)
    contract_dir = DATA_ROOT_PATH / cid
    contract_dir.mkdir(parents=True, exist_ok=True)
    return contract_dir


def save_metadata(record: ContractRecord) -> Path:
    """
    Guarda los metadatos HTML en bruto en:
      data/contracts/<contract_id>/html_metadata.json
    """
    contract_dir = get_contract_dir(record.contract_id)
    metadata_path = contract_dir / "html_metadata.json"

    # 👇 AQUÍ estaba el problema: antes usabas record.metadata (Pydantic)
    # json.dump(record.metadata, f, ...) → peta
    # Ahora guardamos los datos crudos tal cual vienen del HTML:
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(record.metadata_raw.data, f, ensure_ascii=False, indent=2)

    print(f"[STORE] Metadata RAW guardada en {metadata_path}")
    return metadata_path


def verify_pdfs(record: ContractRecord) -> dict[str, bool]:
    """
    Comprueba que los PDFs registrados en record.pdfs existen en disco.
    """
    statuses: dict[str, bool] = {}
    for key, path_str in record.pdfs.items():
        path = Path(path_str)
        exists = path.is_file()
        statuses[key] = exists
        if not exists:
            print(f"[WARN] PDF esperado no encontrado: {key} → {path}")
    return statuses


def save_contract_record(record: ContractRecord) -> None:
    """
    Punto de entrada de almacenamiento:

    - asegura directorio de contrato
    - guarda metadata RAW
    - verifica que los PDFs existan
    - (futuro) podría actualizar un índice global
    """
    _ = get_contract_dir(record.contract_id)
    save_metadata(record)
    verify_pdfs(record)