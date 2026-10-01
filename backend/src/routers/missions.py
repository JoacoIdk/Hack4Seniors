"""Daily missions with automatically tracked progress."""

from fastapi import APIRouter, HTTPException, status

import config
from dependencies import CurrentUser, StorageDep, not_found
from models import MissionClaimOut, MissionOut
from services import missions, points

router = APIRouter(prefix="/missions", tags=["Missions"])


async def _mission_out(storage, user_id: int, mission: dict) -> dict:
    progress = await missions.progress(storage, user_id, mission)
    return {
        **mission,
        "progress": min(progress, mission["target"]),
        "completed": progress >= mission["target"],
        "claimed": await storage.exists("mission_claims", {"mission_id": mission["id"], "user_id": user_id}),
    }


@router.get("", response_model=list[MissionOut])
async def todays_missions(user: CurrentUser, storage: StorageDep):
    rows = await storage.find("missions", {"date": config.today(), "active": True}, order_by="id")
    return [await _mission_out(storage, user["id"], m) for m in rows]


@router.post("/{mission_id}/claim", response_model=MissionClaimOut)
async def claim_mission(mission_id: int, user: CurrentUser, storage: StorageDep):
    """Collect a completed mission's points. Only today's missions can be claimed."""
    mission = await storage.find_one("missions", {"id": mission_id, "active": True})
    if mission is None:
        raise not_found("Mission")
    if mission["date"] != config.today():
        raise HTTPException(status.HTTP_409_CONFLICT, "This mission is not available today")
    async with storage.transaction() as tx:
        if await tx.exists("mission_claims", {"mission_id": mission_id, "user_id": user["id"]}):
            raise HTTPException(status.HTTP_409_CONFLICT, "Mission already claimed")
        if await missions.progress(tx, user["id"], mission) < mission["target"]:
            raise HTTPException(status.HTTP_409_CONFLICT, "Mission not completed yet")
        _ = await tx.insert("mission_claims", {
            "mission_id": mission_id, "user_id": user["id"], "points": mission["points"], "created_at": config.now(),
        })
        awarded = await points.award(
            tx, user["id"], mission["points"], "mission", reference_type="mission", reference_id=mission_id,
            description=mission["title"],
        )
    return {"mission_id": mission_id, "points_awarded": awarded, "balance": await points.balance(storage, user["id"])}
