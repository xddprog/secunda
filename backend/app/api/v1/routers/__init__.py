from fastapi import APIRouter, Depends

from app.api.dependencies import require_api_key
from app.api.v1.routers.payment import router as payment_router

api_v1_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
api_v1_router.include_router(payment_router)
