import asyncio
import re

from trivia_agent import (
    TriviaAgentConfig,
    create_agent,
    run_agent_iter,
    TriviaQuestionOut,
    TriviaQuestionsOut,
)
from trivia_tools import TriviaTools


def requested_n_questions(prompt: str) -> int:
    m = re.search(r"\b(\d+)\b", prompt)
    if not m:
        return 1
    return max(1, int(m.group(1)))


def render_question(q: TriviaQuestionOut) -> str:
    lines = [q.question]
    for i, opt in enumerate(q.options):
        lines.append(f"  {chr(65 + i)}) {opt}")
    return "\n".join(lines)


def parse_answer(text: str, n_options: int) -> int | None:
    t = (text or "").strip().upper()
    if not t:
        return None
    if len(t) == 1 and "A" <= t <= chr(ord("A") + n_options - 1):
        return ord(t) - ord("A")
    if t.isdigit():
        v = int(t)
        if 1 <= v <= n_options:
            return v - 1
    return None


async def run_agent_question() -> None:
    tools = TriviaTools()
    config = TriviaAgentConfig(model="openai:gpt-4o-mini", name="trivia")
    agent = create_agent(config, tools)

    user_prompt = input('Say e.g. "Let\'s play 3 medium questions from History"\n> ')
    message_history = []

    n = requested_n_questions(user_prompt)

    # ✅ run_agent_iter now returns (result, trace)
    result, trace = await run_agent_iter(
        agent,
        user_prompt,
        result_type=TriviaQuestionsOut,
        message_history=message_history,
        debug_events=False,
        trivia_tools=tools,
    )

    # ✅ Print trace
    if trace:
        print("\n--- Agent trace ---")
        for t in trace:
            print(f"🧠 {t}")
        print("-------------------\n")

    # Normalize
    if n == 1:
        # If you always validate TriviaQuestionsOut, you can also just do:
        # questions = TriviaQuestionsOut.model_validate(result).questions[:1]
        questions = [TriviaQuestionOut.model_validate(result)]
    else:
        batch = TriviaQuestionsOut.model_validate(result)
        questions = batch.questions

    score = 0
    for qi, q in enumerate(questions, start=1):
        print(f"\nQuestion {qi}/{len(questions)}\n")
        print(render_question(q) + "\n")

        ans = input(f"Your answer (A-{chr(65 + len(q.options) - 1)} or 1-{len(q.options)}): ")
        idx = parse_answer(ans, len(q.options))

        if idx is None:
            print(f"\n⚠️ Could not parse your answer. Correct: {q.options[q.correct_index]}")
            continue

        if idx == q.correct_index:
            print("\n✅ Correct!")
            score += 1
        else:
            print(f"\n❌ Wrong. Correct: {q.options[q.correct_index]}")

    print(f"\n🏁 Final score: {score}/{len(questions)}")


def main() -> None:
    asyncio.run(run_agent_question())


if __name__ == "__main__":
    main()