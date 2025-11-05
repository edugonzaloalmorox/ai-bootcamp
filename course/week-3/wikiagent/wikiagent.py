import os
from dotenv import load_dotenv
from openai import OpenAI
from typing import Optional, List, Dict, Any
from tools import wikipedia_search, wikipedia_get_page


class WikipediaAgent:
    """
    Wikipedia agent:
    1. Searches Wikipedia.
    2. Fetches relevant page.
    3. Uses OpenAI API to answer using that content.
    """

    def __init__(self, max_chars: int = 8000):
        # Load environment variables from .env once
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY must be set in the environment or .env file")

        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("AGENT_MODEL", "gpt-4o-mini")
        self.max_chars = max_chars

    def _pick_pages(self, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return hits[:1]

    def answer(self, question: str) -> str:
        hits = wikipedia_search(question)
        if not hits:
            return "I couldn't find anything relevant on Wikipedia for that query."

        selected = self._pick_pages(hits)
        title = selected[0]["title"]
        snippet = selected[0].get("snippet", "")
        raw_text = wikipedia_get_page(title)
        context = raw_text[: self.max_chars]

        prompt = f"""
You are a helpful assistant that answers questions using Wikipedia only.

User question:
{question}

You have the following Wikipedia page:

Title: {title}
Snippet: {snippet}

Content:
\"\"\"{context}\"\"\"

Using ONLY this content, answer the user's question clearly and concisely.
If something is not supported by the text, say you are not sure.
""".strip()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        return response.choices[0].message.content.strip()
