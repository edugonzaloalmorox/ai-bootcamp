# wikiagent.py

import os
from dotenv import load_dotenv

from . import tools
from pydantic_ai import Agent 



# Load .env so OPENAI_API_KEY and AGENT_MODEL are available
load_dotenv()

MODEL_NAME = os.getenv("AGENT_MODEL", "openai:gpt-4o-mini")

AGENT_INSTRUCTIONS = """
You are a Wikipedia research agent.

You can use two tools:

1. wikipedia_search(query: str, limit: int = 5)
   - Call this first to find relevant pages.

2. wikipedia_get_page(title: str)
   - Then call this for 1–3 of the most relevant titles to read their content.

Rules:
- Always call wikipedia_search first, then wikipedia_get_page.
- Answer only using the retrieved page text.
- In your final message, **include explicit references** like:
  (source: <Page Title>)
  for every fact you state.
- If you cannot find the answer, say so clearly.
""".strip()


def build_wikipedia_agent() -> Agent[None, str]:
    """
    Build and return a pydantic-ai Agent that uses the Wikipedia tools.
    """
    agent = Agent[None, str](
        MODEL_NAME,
        name="wikipedia_agent",
        system_prompt=AGENT_INSTRUCTIONS,
        tools=[
            tools.wikipedia_search,
            tools.wikipedia_get_page,
        ],
    )
    return agent


# Optional: convenience function so you can keep a similar API to your old class
def answer_with_wikipedia(question: str) -> str:
    """
    Run the Wikipedia agent synchronously and return the answer text.
    """
    agent = build_wikipedia_agent()
    result = agent.run_sync(question)
    return result.output
