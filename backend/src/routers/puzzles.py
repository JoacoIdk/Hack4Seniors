"""
Daily puzzles. The first correct solve of each puzzle gives points, capped per
day; users can keep playing after the cap without earning more.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

import config
from dependencies import CurrentUser, PageDep, StorageDep, not_found
from models import PuzzleKind, PuzzleOut, PuzzleSolveIn, PuzzleSolveOut
from services import points
from services.puzzles import check_answer

router = APIRouter(prefix="/puzzles", tags=["Puzzles"])


async def _with_play(storage, user_id: int, puzzles: list[dict]) -> list[dict]:
    ids = [p["id"] for p in puzzles]
    plays = {
        p["puzzle_id"]: p
        for p in (await storage.find("puzzle_plays", {"user_id": user_id, "puzzle_id__in": ids}) if ids else [])
    }
    return [
        {**p, "solved": plays.get(p["id"], {}).get("solved", False), "attempts": plays.get(p["id"], {}).get("attempts", 0)}
        for p in puzzles
    ]


async def _get_playable(storage, puzzle_id: int) -> dict:
    # Future puzzles stay hidden until their day.
    puzzle = await storage.find_one("puzzles", {"id": puzzle_id, "active": True, "date__lte": config.today()})
    if puzzle is None:
        raise not_found("Puzzle")
    return puzzle


@router.get("/today", response_model=list[PuzzleOut])
async def todays_puzzles(user: CurrentUser, storage: StorageDep):
    rows = await storage.find("puzzles", {"date": config.today(), "active": True}, order_by="id")
    return await _with_play(storage, user["id"], rows)


@router.get("", response_model=list[PuzzleOut])
async def puzzle_archive(
    user: CurrentUser,
    storage: StorageDep,
    page: PageDep,
    kind: PuzzleKind | None = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
):
    """Past and current puzzles, newest first."""
    today = config.today()
    where = {"active": True, "date__lte": min(to_date, today) if to_date else today}
    if from_date:
        where["date__gte"] = from_date
    if kind:
        where["kind"] = kind
    rows = await storage.find("puzzles", where, order_by=["-date", "id"], limit=page.limit, offset=page.offset)
    return await _with_play(storage, user["id"], rows)


@router.get("/{puzzle_id}", response_model=PuzzleOut)
async def get_puzzle(puzzle_id: int, user: CurrentUser, storage: StorageDep):
    return (await _with_play(storage, user["id"], [await _get_playable(storage, puzzle_id)]))[0]


@router.post("/{puzzle_id}/solve", response_model=PuzzleSolveOut)
async def solve_puzzle(puzzle_id: int, body: PuzzleSolveIn, user: CurrentUser, storage: StorageDep):
    puzzle = await _get_playable(storage, puzzle_id)
    correct = check_answer(puzzle["kind"], puzzle["solution"], body.answer)
    now = config.now()

    async with storage.transaction() as tx:
        play = await tx.find_one("puzzle_plays", {"puzzle_id": puzzle_id, "user_id": user["id"]})
        already_solved = bool(play and play["solved"])
        if play is None:
            play = await tx.insert("puzzle_plays", {
                "puzzle_id": puzzle_id, "user_id": user["id"], "attempts": 0, "solved": False,
                "solved_at": None, "solved_day": None, "points_awarded": 0, "created_at": now,
            })
        if not already_solved:
            play = (await tx.increment("puzzle_plays", {"id": play["id"]}, {"attempts": 1}))[0]

        awarded = 0
        if correct and not already_solved:
            awarded = min(config.PUZZLE_POINTS_PER_SOLVE, await points.puzzle_points_available(tx, user["id"]))
            _ = await tx.update("puzzle_plays", {"id": play["id"]}, {
                "solved": True, "solved_at": now, "solved_day": config.today(), "points_awarded": awarded,
            })
            _ = await points.award(
                tx, user["id"], awarded, "puzzle", reference_type="puzzle", reference_id=puzzle_id,
                description=puzzle["title"],
            )
        today_total = await points.earned_today(tx, user["id"], "puzzle")

    return {
        "correct": correct,
        "already_solved": already_solved,
        "attempts": play["attempts"],
        "points_awarded": awarded,
        "puzzle_points_today": today_total,
        "puzzle_points_remaining_today": max(0, config.PUZZLE_POINTS_DAILY_MAX - today_total),
    }
