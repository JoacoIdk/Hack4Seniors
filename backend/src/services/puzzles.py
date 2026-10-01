"""
Puzzle answer checking.

Answers are compared after normalization, so the same rules work for every
puzzle kind as long as the stored solution has the same shape as the answer:

- chess:      ["Qh5", "Nf6", "Qxf7#"] or "Qh5 Nf6 Qxf7#" (check/annotation marks ignored)
- crossword:  {"1A": "casa", "2D": "sol"} or a list of grid rows
- sudoku:     9x9 list of ints
- trivia:     "b" / 2 / "Santiago"
- any kind:   {"any_of": [answer1, answer2]} to accept alternatives
"""

from typing import Any


def _normalize(value: Any, kind: str) -> Any:
    if isinstance(value, str):
        text = " ".join(value.strip().lower().split())
        if kind == "chess":
            text = text.translate(str.maketrans("", "", "+#!?"))
        return text
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_normalize(v, kind) for v in value]
    if isinstance(value, dict):
        return {str(k).strip().lower(): _normalize(v, kind) for k, v in value.items()}
    return value


def check_answer(kind: str, solution: Any, answer: Any) -> bool:
    if isinstance(solution, dict) and set(solution) == {"any_of"}:
        return any(check_answer(kind, option, answer) for option in solution["any_of"])
    # Chess move lists may be submitted as a single space-separated string.
    if kind == "chess":
        if isinstance(solution, str):
            solution = solution.split()
        if isinstance(answer, str):
            answer = answer.split()
    return _normalize(solution, kind) == _normalize(answer, kind)
