import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient


# Explicitly load .env
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def get_qdrant_client() -> QdrantClient:
    """
    Return a Qdrant client configured from environment variables.

    Expected variables:
      - QDRANT_URL
      - QDRANT_API_KEY (for Qdrant Cloud)
    """
    url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    api_key = os.environ.get("QDRANT_API_KEY")

    if api_key:
        return QdrantClient(url=url, api_key=api_key)

    return QdrantClient(url=url)