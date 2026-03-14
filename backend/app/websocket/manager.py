from fastapi import WebSocket

class ConnectionManager:

    def __init__(self):
        self.dashboard_connections: list[WebSocket] = []
        self.worker_connections: dict[int, WebSocket] = {}

    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.dashboard_connections.append(websocket)
        print("dashboard connected:", len(self.dashboard_connections))

    async def connect_worker(self, websocket: WebSocket, operator_id: int):
        await websocket.accept()
        self.worker_connections[operator_id] = websocket

    def disconnect_dashboard(self, websocket: WebSocket):
        if websocket in self.dashboard_connections:
            self.dashboard_connections.remove(websocket)

    def disconnect_worker(self, operator_id: int):
        if operator_id in self.worker_connections:
            del self.worker_connections[operator_id]

    async def send_to_dashboard(self, data):
        dead = []
    
        for ws in self.dashboard_connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
    
        for ws in dead:
            self.dashboard_connections.remove(ws)

    async def send_to_worker(self, operator_id: int, data):
        ws = self.worker_connections.get(operator_id)
        if ws:
            await ws.send_json(data)
    async def broadcast(self, message: dict):
        for connection in self.worker_connections.values():
            await connection.send_json(message)

manager = ConnectionManager()