from datetime import date
from fastapi import APIRouter, Depends, Query, Request
from fastapi.exceptions import HTTPException

from app.services.stats_service import StatsQueryService

router = APIRouter(prefix="/stats", tags=["stats"])

def get_stats_query_service(request: Request) -> StatsQueryService:
    return StatsQueryService(
        redis=request.app.state.redis_api,
        mongo=request.app.state.mongo_api,
    )


@router.get("")
async def get_stats(
    from_date: date = Query(...),
    to_date: date = Query(...),
    service: StatsQueryService = Depends(get_stats_query_service),
):
    if from_date > to_date:
        raise HTTPException(400, "from_date must be <= to_date")

    data = await service.get_range(from_date, to_date)
    return {"data": data}
