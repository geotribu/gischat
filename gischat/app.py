import json
import logging
import os
import sys

import colorlog
import sentry_sdk
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from gischat import INTERNAL_MESSAGE_AUTHOR
from gischat.models import (
    InternalMessageModel,
    MessageModel,
    RulesModel,
    StatusModel,
    VersionModel,
)
from gischat.utils import get_poetry_version

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

    connections: dict[str, list[WebSocket]]

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

    async def push(self, msg: str) -> None:
        await self.generator.asend(msg)

    async def connect(self, room: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[room].append(websocket)

    def remove(self, room: str, websocket: WebSocket) -> None:
        if websocket in self.connections[room]:
            self.connections[room].remove(websocket)

    async def notify(self, room: str, message: str) -> None:
        living_connections = []
        while len(self.connections[room]) > 0:
            # Looping like this is necessary in case a disconnection is handled
            # during await websocket.send_text(message)
            websocket = self.connections[room].pop()
            try:
                await websocket.send_text(message)
                living_connections.append(websocket)
            except WebSocketDisconnect:
                logger.error("Can not send message to disconnected websocket")
        self.connections[room] = living_connections

    def get_nb_users(self, room: str) -> int:
        return len(self.connections[room])

    async def notify_internal(self, room: str) -> None:
        message = InternalMessageModel(
            author=INTERNAL_MESSAGE_AUTHOR, nb_users=self.get_nb_users(room)
        )
        await self.notify(room, json.dumps(jsonable_encoder(message)))


notifier = WebsocketNotifier()


if "SENTRY_DSN" in os.environ and os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN"),
        environment=os.environ.get("ENVIRONMENT", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", 1)),
        profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", 1)),
    )


app = FastAPI(
    title="gischat API",
    summary="Chat with your GIS tribe in QGIS, QField and other clients !",
    version=get_poetry_version(),
)
templates = Jinja2Templates(directory="gischat/templates")


@app.get("/", response_class=HTMLResponse)
async def get_ws_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="ws-page.html",
    )


@app.get("/version", response_model=VersionModel)
async def get_version() -> VersionModel:
    return VersionModel(version=get_poetry_version())


@app.get("/status", response_model=StatusModel)
async def get_status() -> StatusModel:
    return StatusModel(
        status="ok",
        healthy=True,
        rooms=[
            {"name": k, "nb_connected_users": len(v)}
            for k, v in notifier.connections.items()
        ],
    )


@app.get("/rooms", response_model=list[str])
async def get_rooms() -> list[str]:
    return available_rooms()


@app.get("/rules", response_model=RulesModel)
async def get_rules() -> RulesModel:
    return RulesModel(
        rules=os.environ.get("RULES", "YOLO"),
        main_lang=os.environ.get("MAIN_LANG", "en"),
        min_author_length=int(os.environ.get("MIN_AUTHOR_LENGTH", 3)),
        max_author_length=int(os.environ.get("MAX_AUTHOR_LENGTH", 32)),
        max_message_length=int(os.environ.get("MAX_MESSAGE_LENGTH", 255)),
    )


@app.put(
    "/room/{room}/message",
    response_model=MessageModel,
)
async def put_message(room: str, message: MessageModel) -> MessageModel:
    if room not in notifier.connections.keys():
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")
    logger.info(f"Message in room '{room}': {message}")
    await notifier.notify(room, json.dumps(jsonable_encoder(message)))
    return message


@app.websocket("/room/{room}/ws")
async def websocket_endpoint(websocket: WebSocket, room: str) -> None:

    # check if room is registered
    if room not in notifier.connections.keys():
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")

    await notifier.connect(room, websocket)
    await notifier.notify_internal(room)
    logger.info(f"New websocket connected in room '{room}'")

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = MessageModel(**json.loads(data))
            except ValidationError:
                logger.error("Invalid message in websocket")
                continue
            logger.info(f"Message in room '{room}': {message}")
            try:
                await notifier.notify(room, json.dumps(jsonable_encoder(message)))
            except WebSocketDisconnect:
                logger.error("Can not send message to disconnected websocket")
    except WebSocketDisconnect:
        notifier.remove(room, websocket)
        await notifier.notify_internal(room)
        logger.info(f"Websocket disconnected from room '{room}'")
