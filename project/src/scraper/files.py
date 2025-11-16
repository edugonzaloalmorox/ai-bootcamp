

import os
import re
from typing import Optional

import requests

from .config import HEADERS


def safe_filename(name: Optional[str]) -> str:
    """Limpia cadenas para que sean nombres de archivo válidos."""
    if not name:
        return "unknown"
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_") or "unknown"


def download_pdf(url: str, dest_path: str, timeout: int = 60) -> bool:
    """
    Descarga un PDF a dest_path.
    Devuelve True si se descarga correctamente.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        print(f"[PDF] Error descargando {url}: {e}")
        return False

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    with open(dest_path, "wb") as f:
        f.write(resp.content)

    print(f"[PDF] Guardado en {dest_path}")
    return True
