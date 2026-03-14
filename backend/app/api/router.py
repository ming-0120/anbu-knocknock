from fastapi import APIRouter
from app.api.dashboard import router as dashboard_router
from app.api.hourly_features import router as hourly_router
from app.api.operator_router import router as operator_router
from app.api.operator_tasks import router as operator_tasks_router
from app.websocket.router import router as websocket_router
from app.api.alert_actions import router as alert_action_router
from app.api.call_router import router as call_router
api_router = APIRouter()
api_router.include_router(dashboard_router)
api_router.include_router(hourly_router)
api_router.include_router(operator_router)
api_router.include_router(operator_tasks_router)
api_router.include_router(websocket_router)
api_router.include_router(alert_action_router)
api_router.include_router(call_router)
