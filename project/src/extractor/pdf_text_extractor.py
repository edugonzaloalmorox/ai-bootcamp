from dataclasses import dataclass
from typing import BinaryIO, List, Optional

import io
import logging

import PyPDF2
import requests

logger = logging.getLogger(__name__)


# --------- Data models ---------


@dataclass
class PageText:
    """
    Represents the text extracted from a single PDF page.

    Attributes
    ----------
    page_number : int
        Zero-based page index.
    text : str
        Plain text extracted from that page.
    """
    page_number: int
    text: str


@dataclass
class PdfText:
    """
    Represents the textual content of a full PDF document.

    Attributes
    ----------
    source : str
        Logical source identifier (e.g., URL or file path).
    num_pages : int
        Total number of pages in the PDF.
    pages : List[PageText]
        Text extracted for each page.
    """
    source: str
    num_pages: int
    pages: List[PageText]


class PdfTextExtractionError(Exception):
    """Raised when the PDF cannot be read or text cannot be extracted."""
    pass


class PdfDownloadError(Exception):
    """Raised when the PDF cannot be downloaded from a remote source."""
    pass




def extract_text_from_file(file_obj: BinaryIO, source: str = "<file>") -> PdfText:
    """
    Extracts text from all pages of a PDF given a file-like object.

    Parameters
    ----------
    file_obj : BinaryIO
        File-like object opened in binary read mode (e.g. `open(..., "rb")`
        or an `io.BytesIO` instance).
    source : str, default "<file>"
        Logical identifier for the PDF source (path, URL, etc.).

    Returns
    -------
    PdfText
        Structured representation of the PDF text.

    Raises
    ------
    PdfTextExtractionError
        If the PDF is corrupted or cannot be read.
    """
    try:
        reader = PyPDF2.PdfReader(file_obj)
    except Exception as exc:  # noqa: BLE001
        raise PdfTextExtractionError(f"Failed to read PDF: {exc}") from exc

    pages: List[PageText] = []

    for i, page in enumerate(reader.pages):
        try:
            raw_text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            raise PdfTextExtractionError(
                f"Error extracting text from page {i}: {exc}"
            ) from exc

        # Simple normalization: strip and normalize line endings
        normalized = "\n".join(
            line.rstrip()
            for line in raw_text.splitlines()
        ).strip()

        pages.append(PageText(page_number=i, text=normalized))

    return PdfText(
        source=source,
        num_pages=len(pages),
        pages=pages,
    )


def extract_text_from_bytes(data: bytes, source: str = "<bytes>") -> PdfText:
    """
    Extracts text from a PDF given its raw bytes.

    Parameters
    ----------
    data : bytes
        Raw binary content of the PDF.
    source : str, default "<bytes>"
        Logical identifier for the PDF source (path, URL, etc.).

    Returns
    -------
    PdfText
        Structured representation of the PDF text.
    """
    buffer = io.BytesIO(data)
    return extract_text_from_file(buffer, source=source)


def extract_text_from_path(path: str) -> PdfText:
    """
    Extracts text from a PDF located at a filesystem path.

    Parameters
    ----------
    path : str
        Filesystem path to the PDF file.

    Returns
    -------
    PdfText
        Structured representation of the PDF text.
    """
    with open(path, "rb") as f:
        return extract_text_from_file(f, source=path)


# --------- Download + high-level helpers ---------


def download_pdf(url: str, timeout: int = 20) -> bytes:
    """
    Downloads a PDF from a remote HTTP(S) URL.

    Parameters
    ----------
    url : str
        URL pointing to the PDF resource.
    timeout : int, default 20
        Timeout in seconds for the HTTP request.

    Returns
    -------
    bytes
        Raw binary content of the downloaded PDF.

    Raises
    ------
    PdfDownloadError
        If the HTTP request fails or returns a non-200 status code.
    """
    try:
        logger.debug("Downloading PDF from URL: %s", url)
        resp = requests.get(url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        raise PdfDownloadError(f"Failed to download PDF from {url}: {exc}") from exc

    if resp.status_code != 200:
        raise PdfDownloadError(
            f"Failed to download PDF from {url}: HTTP {resp.status_code}"
        )

    content_type = resp.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower():
        logger.warning(
            "Content-Type for %s does not look like PDF: %s",
            url,
            content_type,
        )

    return resp.content


def extract_text_from_url(url: str, timeout: int = 20) -> PdfText:
    """
    Downloads a PDF from a URL and extracts its text.

    Parameters
    ----------
    url : str
        URL pointing to the PDF resource.
    timeout : int, default 20
        Timeout in seconds for the HTTP request.

    Returns
    -------
    PdfText
        Structured representation of the PDF text.
    """
    pdf_bytes = download_pdf(url, timeout=timeout)
    return extract_text_from_bytes(pdf_bytes, source=url)
