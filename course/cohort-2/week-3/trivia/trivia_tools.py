import html
import random
from typing import Any, Dict, List, Optional

import requests


class TriviaTools:
    BASE_URL = "https://opentdb.com"

    def __init__(self, *, timeout_s: float = 10.0, rng: Optional[random.Random] = None) -> None:
        # Store last tool payload for the agent runner to read deterministically
        self.last_questions_payload: Optional[Dict[str, Any]] = None
        self._timeout_s = timeout_s
        self._rng = rng or random.Random()

    def get_categories(self) -> List[Dict[str, Any]]:
        print("🛠 Executing get_categories()")

        url = f"{self.BASE_URL}/api_category.php"
        try:
            resp = requests.get(url, timeout=self._timeout_s)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch categories from OpenTDB: {e}") from e

        cats = data.get("trivia_categories", [])
        print(f"🛠 Returned {len(cats)} categories")
        return cats

    def get_questions(self, amount: int, category: int, difficulty: str) -> Dict[str, Any]:
        """Fetch trivia questions as structured data (NOT a formatted string)."""

        print(
            f"🛠 Executing get_questions(amount={amount}, "
            f"category={category}, difficulty={difficulty})"
        )

        # Basic input normalization/validation
        amount = int(amount)
        if amount < 1:
            raise ValueError("amount must be >= 1")

        difficulty = (difficulty or "").strip().lower()
        if difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("difficulty must be one of: easy, medium, hard")

        params = {
            "amount": amount,
            "category": int(category),
            "difficulty": difficulty,
            "type": "multiple",
        }

        try:
            resp = requests.get(f"{self.BASE_URL}/api.php", params=params, timeout=self._timeout_s)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch questions from OpenTDB: {e}") from e

        # OpenTDB returns response_code; 0 means success
        rc = data.get("response_code")
        if rc != 0:
            # 1 = no results, 2 = invalid param, 3 = token not found, 4 = token empty
            raise RuntimeError(f"OpenTDB returned response_code={rc} for params={params}")

        results = data.get("results", [])
        if not results:
            raise RuntimeError(f"OpenTDB returned 0 questions for params={params}")

        questions: List[Dict[str, Any]] = []
        for q in results:
            question = html.unescape(q.get("question", ""))
            correct = html.unescape(q.get("correct_answer", ""))
            wrong = [html.unescape(a) for a in (q.get("incorrect_answers") or [])]

            # Defensive: ensure we have at least 1 correct + 1 wrong
            if not question or not correct or len(wrong) < 1:
                continue

            options = wrong + [correct]
            self._rng.shuffle(options)
            correct_index = options.index(correct)

            questions.append(
                {
                    "category_id": int(category),
                    "category_name": q.get("category"),
                    "difficulty": q.get("difficulty", difficulty),
                    "question": question,
                    "options": options,
                    "correct_index": correct_index,
                }
            )

        if not questions:
            raise RuntimeError("OpenTDB returned malformed questions (after cleaning, no valid items).")

        print("🛠 Question fetched successfully")

        payload = {"questions": questions}
        self.last_questions_payload = payload
        return payload