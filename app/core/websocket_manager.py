import logging
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}


    async def connect(self, socket_id: str, websocket: WebSocket):
        await websocket.accept()
        if socket_id not in self.active_connections:
            self.active_connections[socket_id] = []
        self.active_connections[socket_id].append(websocket)
        logger.info(f"Nouveau WebSocket pour l'ID: {socket_id}")


    def disconnect(self, socket_id: str, websocket: WebSocket):
        if socket_id in self.active_connections:
            if websocket in self.active_connections[socket_id]:
                self.active_connections[socket_id].remove(websocket)
            
            if not self.active_connections[socket_id]:
                del self.active_connections[socket_id]
        logger.info(f"Déconnexion du WebSocket pour l'ID: {socket_id}")


    async def send_update(self, socket_id: str, message: dict):
        if socket_id not in self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections[socket_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Erreur d'envoi WebSocket pour {socket_id}: {e}")
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(socket_id, dead)


manager = ConnectionManager()