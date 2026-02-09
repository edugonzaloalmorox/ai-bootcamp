import requests
from typing import List, Dict, Any

WIKIPEDIA_API_SEARCH = (
    "https://en.wikipedia.org/w/api.php"
)
WIKIPEDIA_API_PAGE = (
    "https://en.wikipedia.org/w/index.php"
)

HEADERS = {
   "User-Agent": "WebFetch/0.1"
}

def wikipedia_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Use the Wikipedia search API to find pages related to a query.
    Returns a list of search hits (dicts with title, snippet, etc.).
    """
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,  # requests will handle encoding; no need for replace(" ", "+")
        "srlimit": limit,
    }
    resp = requests.get(
        WIKIPEDIA_API_SEARCH,
        params=params,
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("query", {}).get("search", [])


def wikipedia_get_page(title: str) -> str:
    """
    Get the raw wikitext of a Wikipedia page given its title.
    """
    params = {
        "title": title,
        "action": "raw",
    }
    resp = requests.get(
        WIKIPEDIA_API_PAGE,
        params=params,
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.text