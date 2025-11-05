from wikiagent import WikipediaAgent


def main() -> None:
    agent = WikipediaAgent()

    question = "what is the player with more matches played for England national football team?"
    answer = agent.answer(question)

    print(f"Q: {question}")
    print("A:", answer)


if __name__ == "__main__":
    main()