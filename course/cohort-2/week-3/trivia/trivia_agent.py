

import json
import asyncio
from dataclasses import dataclass
from typing import Any, Literal, Optional, Type, TypeVar, Tuple
import contextlib
import io

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import FunctionToolCallEvent

from trivia_tools import TriviaTools

load_dotenv()

# ----------------------------
# Structured output (agent -> main)
# ----------------------------

Difficulty = Literal["easy", "medium", "hard"]


class TriviaQuestionOut(BaseModel):
    category_id: int
    category_name: Optional[str] = None
    difficulty: Difficulty
    question: str
    options: list[str] = Field(min_length=2, max_length=6)
    correct_index: int = Field(ge=0)

class TriviaQuestionsOut(BaseModel):
    questions: list[TriviaQuestionOut]

class TriviaRunOut(BaseModel):
    trace: list[str] = Field(default_factory=list)
    questions: list[TriviaQuestionOut] = Field(min_length=1)


DEFAULT_INSTRUCTIONS = """
- Use tools to fetch trivia questions.
-Return ONLY JSON matching TriviaRunOut. trace must include short bullets explaining decisions:
- parsed requested number/difficulty/category
- selected category_id
- called get_questions with params
No hidden reasoning, just a brief explanation.
- If the user asks for ONE question, return TriviaQuestionOut.
- If the user asks for MULTIPLE questions, return TriviaQuestionsOut:
  {"questions": [TriviaQuestionOut, ...]}

No markdown. No prose. No extra keys.

""".strip()



# ----------------------------
# Config + agent factory
# ----------------------------

@dataclass(frozen=True)
class TriviaAgentConfig:
    model: str = "openai:gpt-4o-mini"
    name: str = "trivia"
    system_prompt: str = DEFAULT_INSTRUCTIONS


def create_agent(config: TriviaAgentConfig, trivia_tools: TriviaTools) -> Agent:
    async def get_categories():
        return await asyncio.to_thread(trivia_tools.get_categories)

    async def get_questions(amount: int, category: int, difficulty: str):
        return await asyncio.to_thread(trivia_tools.get_questions, amount, category, difficulty)

    tools = [get_categories, get_questions]
    return Agent(
        name=config.name,
        model=config.model,
        system_prompt=config.system_prompt,
        tools=tools,
    )


# ----------------------------
# Helpers (final extraction)
# ----------------------------

T = TypeVar("T")


def _first_attr(obj: Any, *names: str) -> Any:
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    return None


def _looks_like_json(s: str) -> bool:
    s = s.lstrip()
    return s.startswith("{") or s.startswith("[")


async def _get_final_from_run(agent_run: Any) -> Any:
    """
    Extract the final result-like object from agent_run across pydantic-ai versions.
    """
    final = _first_attr(agent_run, "result", "final_result", "data")
    if final is not None:
        return final

    get_data = getattr(agent_run, "get_data", None)
    if callable(get_data):
        return await get_data()

    raise RuntimeError("Agent run completed but no final result was found on agent_run.")


def _extract_payload(final: Any) -> Any:
    """
    Given a final object (possibly AgentRunResult-like), extract structured payload.
    """
    data = _first_attr(final, "data")
    if data is not None:
        return data

    output = _first_attr(final, "output", "output_text")
    if output is not None:
        return output

    return final



# ----------------------------
# Iterative runner (iter + tools)
# ----------------------------

async def _spinner(label: str, done: asyncio.Event) -> None:
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    i = 0
    while not done.is_set():
        print(f"\r{label} {frames[i % len(frames)]}", end="", flush=True)
        i += 1
        await asyncio.sleep(0.08)
    print(f"\r{label} ✅", flush=True)


async def run_agent_iter(
    agent: Agent,
    user_prompt: str,
    *,
    result_type: Type[T],
    message_history: Optional[list[Any]] = None,
    debug_events: bool = False,
    trivia_tools=None,
) -> Tuple[T, list[str]]:
    if message_history is None:
        message_history = []

    trace: list[str] = [f"User request: {user_prompt}"]

    print("\n🚀 Starting agent run (iter stream)...\n")

    async with agent.iter(user_prompt, message_history=message_history) as agent_run:
        async for node in agent_run:
            if Agent.is_model_request_node(node):
                if debug_events:
                    print(f"\n🧠 MODEL ({agent.name}) thinking...\n")

                async with node.stream(agent_run.ctx) as stream:
                    async for chunk in stream.stream_text(delta=True):
                        if debug_events:
                            print(chunk, end="", flush=True)
                        # don’t add raw model tokens to trace; it’s noisy/unreliable

                if debug_events:
                    print()

            elif Agent.is_call_tools_node(node):
                spinner_label = "Running tools"
                saw_tool_call = False

                try:
                    async with node.stream(agent_run.ctx) as events:
                        async for event in events:
                            if isinstance(event, FunctionToolCallEvent):
                                saw_tool_call = True
                                tool_name = event.part.tool_name
                                args = event.part.args
                                print(f"  🔧 TOOL CALL ({agent.name}): {tool_name}({args})")
                                trace.append(f"Tool call: {tool_name}({args})")
                                spinner_label = f"Executing {tool_name}"
                except TypeError:
                    pass

                # If no tool calls, don't spin/execute/trace
                if not saw_tool_call:
                    continue

                done = asyncio.Event()
                spin_task = asyncio.create_task(_spinner(spinner_label, done))
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        if hasattr(node, "run"):
                            await node.run(agent_run.ctx)
                        elif hasattr(node, "execute_tools"):
                            await node.execute_tools(agent_run.ctx)
                        elif hasattr(node, "execute"):
                            await node.execute(agent_run.ctx)
                        else:
                            raise TypeError("CallToolsNode has no known execution method.")
                    trace.append("Tool execution complete")
                finally:
                    done.set()
                    await spin_task

            else:
                if debug_events:
                    print(f"[node] {type(node).__name__}")

    if trivia_tools is None or getattr(trivia_tools, "last_questions_payload", None) is None:
        raise RuntimeError(
            "No questions payload available. Ensure TriviaTools.get_questions sets "
            "`self.last_questions_payload` before returning."
        )

    payload = trivia_tools.last_questions_payload
    # Helpful trace detail
    if isinstance(payload, dict) and "questions" in payload and isinstance(payload["questions"], list):
        trace.append(f"Received {len(payload['questions'])} questions")

    result = payload if isinstance(payload, result_type) else result_type.model_validate(payload)
    return result, trace