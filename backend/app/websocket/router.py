from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect
from app.websocket.manager import manager
import asyncio
router = APIRouter()

@router.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):

    await manager.connect_dashboard(websocket)

    try:
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)
    except Exception:
        manager.disconnect_dashboard(websocket)


@router.websocket("/ws/worker/{operator_id}")
async def worker_ws(websocket: WebSocket, operator_id: int):

    await manager.connect_worker(websocket, operator_id)

    try:
        while True:
            await websocket.receive_text()
    except:
        manager.disconnect_worker(operator_id)

@router.websocket("/ws/operators")
async def operator_ws(ws: WebSocket):
    await manager.connect_dashboard(ws)

    try:
        while True:
            await ws.receive_text()
    except:
        manager.disconnect_dashboard(ws)       