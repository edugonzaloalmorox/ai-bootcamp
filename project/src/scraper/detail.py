import os
from typing import Dict, Optional

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .config import BASE_URL, DATA_ROOT
from .files import safe_filename, download_pdf
from .html import fetch_html
from .html_metadata import extract_metadata_from_html

from src.contracts.models import ContractRecord, ContractMetadataRaw, ContractMetadataCanonical
from src.contracts.storage import save_contract_record


def extract_pliego_pdfs_from_soup(
    soup: BeautifulSoup,
    base_url: str = BASE_URL,
) -> Dict[str, str]:
    """
    Extrae específicamente los PDFs de pliego administrativo y pliego técnico
    a partir de la sección 'Pliegos de condiciones'.

    Estructura esperada:
      - contenedor con id="pcon-pliego-de-condiciones"
      - dentro, varios <div> hermanos:
          div[1] -> Pliego de cláusulas administrativas particulares
          div[2] -> Pliego de prescripciones técnicas particulares
          div[3] -> Documento adicional (si lo hay)

    Dentro de cada <div> hay un enlace 'Descargar'.

    Devuelve:
      {
        "pliego_admin": "https://.../download",
        "pliego_tecnico": "https://.../download"
      }

    Si alguno falta, no se incluye la clave.
    """
    pdf_links: Dict[str, str] = {}

    container = soup.find(id="pcon-pliego-de-condiciones")
    if not container:
        print("[WARN] No se encontró el contenedor 'pcon-pliego-de-condiciones'")
        return pdf_links

    # Tomamos solo los hijos directos tipo <div>
    divs = [child for child in container.find_all(recursive=False) if child.name == "div"]

    def first_descargar_link(div) -> Optional[str]:
        for a in div.find_all("a", href=True):
            text = (a.get_text(strip=True) or "").lower()
            if "descargar" in text:
                return urljoin(base_url, a["href"])
        return None

    # div[1] -> pliego administrativo
    if len(divs) >= 1:
        href_admin = first_descargar_link(divs[0])
        if href_admin:
            pdf_links["pliego_admin"] = href_admin

    # div[2] -> pliego técnico
    if len(divs) >= 2:
        href_tecnico = first_descargar_link(divs[1])
        if href_tecnico:
            pdf_links["pliego_tecnico"] = href_tecnico

    if "pliego_admin" not in pdf_links:
        print("[WARN] No se encontró enlace a pliego_admin en esta página.")
    if "pliego_tecnico" not in pdf_links:
        print("[WARN] No se encontró enlace a pliego_tecnico en esta página.")

    return pdf_links


def get_contract_id_from_metadata(metadata: Dict[str, Optional[str]]) -> Optional[str]:
    """
    Intenta obtener un identificador estable de contrato.
    Preferimos 'Número de expediente'; se podría extender.
    """
    for key, value in metadata.items():
        if value and ("Número de expediente" in key or "Número expediente" in key):
            return value
    return None


def process_contract_detail(url: str) -> ContractRecord:
    """
    Descarga la página de detalle, extrae:
      - metadatos de convocatoria (raw + canónicos)
      - PDFs de pliego administrativo y técnico
      - descarga los PDFs en disco organizados por contract_id

    Devuelve un ContractRecord pydantic.
    """
    print(f"\n[CONTRACT] Procesando {url}")

    # 1) Descargamos HTML UNA sola vez
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    # 2) Metadatos brutos extraídos del HTML (dict)
    metadata_dict = extract_metadata_from_html(html)

    # 3) Wrappers Pydantic: raw + canonical
    metadata_raw = ContractMetadataRaw(data=metadata_dict)
    metadata_canonical = ContractMetadataCanonical.from_raw(metadata_raw)

    # 4) contract_id a partir de la metadata canónica (o fallback)
    contract_id = metadata_canonical.contract_id or "unknown"
    contract_id_clean = safe_filename(contract_id)

    contract_dir = os.path.join(DATA_ROOT, contract_id_clean)
    os.makedirs(contract_dir, exist_ok=True)

    # 5) Enlaces específicos de pliegos
    pdf_links = extract_pliego_pdfs_from_soup(soup)

    pdf_local_paths: Dict[str, str] = {}
    for key in ("pliego_admin", "pliego_tecnico"):
        url_pdf = pdf_links.get(key)
        if not url_pdf:
            continue

        filename = f"{key}.pdf"
        dest_path = os.path.join(contract_dir, filename)
        if download_pdf(url_pdf, dest_path):
            pdf_local_paths[key] = dest_path

    # 6) Construimos el ContractRecord
    record = ContractRecord(
        contract_id=contract_id,
        detail_url=url,
        metadata_raw=metadata_raw,
        metadata=metadata_canonical,
        pdfs=pdf_local_paths,
    )

    # 7) Guardamos y verificamos (si ya tienes storage)
    save_contract_record(record)  

    return record

    
    
    
    
    
