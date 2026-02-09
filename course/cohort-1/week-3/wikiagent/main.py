
from wikiagent import build_wikipedia_agent

def main() -> None:
    agent = build_wikipedia_agent()
    question = "where do capybaras live?"
    result = agent.run_sync(question)
    output = getattr(result, "output", None)
    print(f"Q: {question}")
    if output is None:
        output = getattr(result, "data", None)

    print("A:", output)

   


if __name__ == "__main__":
    main()