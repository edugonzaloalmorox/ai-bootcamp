# src/scraper/html.py

import re
import time
from typing import List, Set
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import requests

from .config import HEADERS, BASE_URL


def fetch_html(url: str, timeout: int = 30) -> str:
    """Fetch raw HTML from a URL using requests."""
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def extract_contract_links(html: str) -> List[str]:
    """
    Extract links starting with /contrato-publico/.
    Normalize to absolute URLs. Return unique list.
    """
    pattern = r'href="(/contrato-publico/[^"]+)"'
    matches = re.findall(pattern, html)
    return sorted({BASE_URL + path for path in matches})


def update_page(url: str, page: int) -> str:
    """Replace the `page` parameter in the URL with a new value."""
    parts = urlparse(url)
    q = parse_qs(parts.query, keep_blank_values=True)
    q["page"] = [str(page)]
    new_query = urlencode(q, doseq=True)
    return urlunparse(parts._replace(query=new_query))


def paginate_contract_links(
    base_url: str,
    max_pages: int = 20,
    sleep_secs: float = 0.8,
    stop_when_empty: bool = True,
) -> List[str]:
    """
    Crawl pages ?page=0..N and collect all contract links.
    """
    seen: Set[str] = set()

    for page in range(max_pages):
        url = update_page(base_url, page)
        html = fetch_html(url)
        links = extract_contract_links(html)

        before = len(seen)
        seen.update(links)
        added = len(seen) - before
        print(f"[page {page}] found={len(links)} added={added} total={len(seen)}")

        if stop_when_empty and len(links) == 0:
            print("No links found → stopping early.")
            break

        time.sleep(sleep_secs)

    return sorted(seen)
