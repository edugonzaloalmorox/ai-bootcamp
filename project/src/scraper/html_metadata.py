from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {"User-Agent": "html-metadata-extractor/1.0"}


def _parse_convocatoria_from_soup(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """
    Parsea la lista <ul class='pcon-convocatoria'> en la página de detalle
    y devuelve un diccionario {etiqueta: valor}.

    Este parser es independiente de la descarga; se puede usar tanto
    con HTML recién bajado como con HTML leído de disco.
    """
    data: Dict[str, Optional[str]] = {}

    ul = soup.select_one("ul.pcon-convocatoria")
    if not ul:
        return data

    for li in ul.find_all("li", recursive=False):
        label_el = li.select_one(".field__label")
        if not label_el:
            continue

        label = label_el.get_text(strip=True)

        # Preferimos .field__item, pero caemos a .field-content si no existe
        value_el = li.select_one(".field__item") or li.select_one(".field-content")
        if value_el:
            value = " ".join(value_el.stripped_strings)
        else:
            value = None

        data[label] = value

    return data


def extract_metadata_from_html(html: str) -> Dict[str, Optional[str]]:
    """
    Extrae los metadatos de la convocatoria de un detalle de contrato
    a partir de HTML crudo.
    """
    soup = BeautifulSoup(html, "html.parser")
    return _parse_convocatoria_from_soup(soup)


def extract_metadata_from_url(
    url: str,
    timeout: int = 30,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Optional[str]]:
    """
    Descarga la página de detalle de un contrato y extrae los metadatos
    de la convocatoria.

    Devuelve un diccionario {etiqueta: valor}, por ejemplo:

      {
        "Tipo de publicación": "...",
        "Situación": "...",
        "Número de expediente": "...",
        ...
      }
    """
    hdrs = headers or DEFAULT_HEADERS

    try:
        resp = requests.get(url, headers=hdrs, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        print(f"[HTML-METADATA] Error al descargar {url}: {e}")
        return {}

    resp.encoding = resp.apparent_encoding or "utf-8"
    return extract_metadata_from_html(resp.text)