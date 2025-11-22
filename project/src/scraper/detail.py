import os
import logging
from typing import Dict, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .config import BASE_URL, DATA_ROOT
from .files import safe_filename, download_pdf
from .html import fetch_html
from .html_metadata import extract_metadata_from_html

from src.contracts.models import (
    ContractRecord,
    ContractMetadataRaw,
    ContractMetadataCanonical,
)
from src.contracts.storage import save_contract_record, save_pdf_texts
from src.extractor.pdf_text_extractor import (
    extract_text_from_path,
    PdfText,
    PdfTextExtractionError,
)

logger = logging.getLogger(__name__)


def extract_pliego_pdfs_from_soup(
    soup: BeautifulSoup,
    base_url: str = BASE_URL,
) -> Dict[str, str]:
    """
    Extract administrative and technical tender PDFs from the
    'Pliegos de condiciones' section.

    Expected HTML structure
    -----------------------
    - container with id="pcon-pliego-de-condiciones"
    - inside, several sibling <div> elements:
        div[1] -> Administrative clauses (pliego administrativo)
        div[2] -> Technical specifications (pliego técnico)
        div[3] -> Additional document (optional)

    Each <div> should contain a link with text containing 'Descargar'.

    Returns
    -------
    Dict[str, str]
        Mapping with keys:
          - 'pliego_admin': URL to administrative document
          - 'pliego_tecnico': URL to technical document

        If any of them is missing, the key is not included.
    """
    pdf_links: Dict[str, str] = {}

    container = soup.find(id="pcon-pliego-de-condiciones")
    if not container:
        logger.warning(
            "Container 'pcon-pliego-de-condiciones' not found while extracting pliegos."
        )
        return pdf_links

    # Take only direct children that are <div> elements
    divs = [child for child in container.find_all(recursive=False) if child.name == "div"]

    def first_descargar_link(div) -> Optional[str]:
        for a in div.find_all("a", href=True):
            text = (a.get_text(strip=True) or "").lower()
            if "descargar" in text:
                return urljoin(base_url, a["href"])
        return None

    # div[1] -> administrative PDF
    if len(divs) >= 1:
        href_admin = first_descargar_link(divs[0])
        if href_admin:
            pdf_links["pliego_admin"] = href_admin

    # div[2] -> technical PDF
    if len(divs) >= 2:
        href_tecnico = first_descargar_link(divs[1])
        if href_tecnico:
            pdf_links["pliego_tecnico"] = href_tecnico

    if "pliego_admin" not in pdf_links:
        logger.warning("No 'pliego_admin' link found on this page.")
    if "pliego_tecnico" not in pdf_links:
        logger.warning("No 'pliego_tecnico' link found on this page.")

    return pdf_links


def get_contract_id_from_metadata(metadata: Dict[str, Optional[str]]) -> Optional[str]:
    """
    Try to obtain a stable contract identifier from raw HTML metadata.

    Currently this prefers fields whose key contains 'Número de expediente'.
    This can be extended later to support other field names.
    """
    for key, value in metadata.items():
        if value and ("Número de expediente" in key or "Número expediente" in key):
            return value
    return None


def process_contract_detail(url: str) -> ContractRecord:
    """
    Download a contract detail page and build a ContractRecord.

    The function:
      - downloads the HTML detail page,
      - extracts raw metadata from the HTML,
      - builds raw and canonical Pydantic metadata models,
      - identifies and downloads administrative and technical PDF documents,
      - stores the PDFs under a directory named after the contract_id,
      - extracts text from each PDF and persists it,
      - persists the ContractRecord (via save_contract_record).

    Parameters
    ----------
    url : str
        Detail page URL for the contract.

    Returns
    -------
    ContractRecord
        Pydantic model containing canonical and raw metadata plus local PDF paths.
    """
    logger.info("[CONTRACT] Processing %s", url)

    # 1) Fetch HTML once
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    # 2) Raw metadata extracted from HTML (dict)
    metadata_dict = extract_metadata_from_html(html)

    # 3) Pydantic wrappers: raw + canonical
    metadata_raw = ContractMetadataRaw(data=metadata_dict)
    metadata_canonical = ContractMetadataCanonical.from_raw(metadata_raw)

    # 4) contract_id from canonical metadata (or fallback)
    contract_id = metadata_canonical.contract_id or "unknown"
    contract_id_clean = safe_filename(contract_id)

    contract_dir = os.path.join(DATA_ROOT, contract_id_clean)
    os.makedirs(contract_dir, exist_ok=True)

    # 5) Extract PDF links and download PDFs
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

    # 5.b) Extract text from each downloaded PDF and persist it
    pdf_texts: Dict[str, PdfText] = {}
    for key, path in pdf_local_paths.items():
        try:
            pdf_texts[key] = extract_text_from_path(path)
        except PdfTextExtractionError as exc:
            logger.warning(
                "Failed to extract text from %s (%s): %s",
                key,
                path,
                exc,
            )

    if pdf_texts:
        save_pdf_texts(contract_id, pdf_texts)

    # 6) Build ContractRecord
    record = ContractRecord(
        contract_id=contract_id,
        detail_url=url,
        metadata_raw=metadata_raw,
        metadata=metadata_canonical,
        pdfs=pdf_local_paths,
    )

    # 7) Persist and optionally validate
    save_contract_record(record)

    return record
