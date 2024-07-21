import json
import logging
import os
import sys
from typing import Any

import colorlog
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketDisconnect

from gischat.models import MessageModel
from gischat.utils import get_version
from gischat.ws_html import ws_html

# logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = colorlog.ColoredFormatter(
    "%(yellow)s[%(asctime)s] %(log_color)s[%(levelname)s]%(reset)s %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def available_rooms() -> list[str]:
    return os.environ.get("ROOMS", "QGIS,QField,Geotribu").split(",")


class WebsocketNotifier:
    """
    Class used to broadcast messages to registered websockets
    """

    def __init__(self):
        # registered websockets for rooms
        self.connections: dict[str, list[WebSocket]] = {
            room: [] for room in available_rooms()
        }
        self.generator = self.get_notification_generator()

    async def get_notification_generator(self):
        while True:
            room, message = yield
            await self.notify(room, message)

    async def push(self, msg: str):
        await self.generator.asend(msg)

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[room].append(websocket)

    def remove(self, room: str, websocket: WebSocket):
        self.connections[room].remove(websocket)

    async def notify(self, room: str, message: str):
        living_connections = []
        while len(self.connections[room]) > 0:
            # Looping like this is necessary in case a disconnection is handled
            # during await websocket.send_text(message)
            websocket = self.connections[room].pop()
            await websocket.send_text(message)
            living_connections.append(websocket)
        self.connections[room] = living_connections


notifier = WebsocketNotifier()

app = FastAPI(
    title="gischat API",
    summary="Chat with your GIS tribe in QGIS, QField and other clients !",
    version=get_version(),
)


@app.get("/")
async def get_ws_page():
    return HTMLResponse(ws_html)


@app.get("/version")
async def get_version() -> dict[str, Any]:
    return {"version": get_version()}


@app.get("/status")
async def get_status() -> dict[str, Any]:
    return {
        "status": "ok",
        "healthy": True,
        "rooms": [
            {"name": k, "nb_connected_users": len(v)}
            for k, v in notifier.connections.items()
        ],
    }


@app.get("/rooms")
async def get_rooms() -> list[str]:
    return available_rooms()


@app.put("/room/{room}/message")
async def put_message(room: str, message: MessageModel) -> MessageModel:
    if room not in notifier.connections.keys():
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")
    await notifier.notify(room, json.dumps(jsonable_encoder(message)))
    return message


@app.websocket("/room/{room}/ws")
async def websocket_endpoint(websocket: WebSocket, room: str):
    if room not in notifier.connections.keys():
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")
    await notifier.connect(room, websocket)
    logger.info(f"New websocket connected in room '{room}'")
    try:
        while True:
            data = await websocket.receive_text()
            message = MessageModel(**json.loads(data))
            logger.info(f"Message in room '{room}': {message}")
            await notifier.notify(room, json.dumps(jsonable_encoder(message)))
    except WebSocketDisconnect:
        notifier.remove(room, websocket)
        logger.info(f"Websocket disconnected from room '{room}'")
