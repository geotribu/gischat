import base64
import json
import logging
import os
import sys
from io import BytesIO

import colorlog
import sentry_sdk
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from PIL import Image
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from gischat.models import (
    GischatExiterMessage,
    GischatGeojsonLayerMessage,
    GischatImageMessage,
    GischatLikeMessage,
    GischatMessageModel,
    GischatMessageTypeEnum,
    GischatNbUsersMessage,
    GischatNewcomerMessage,
    GischatTextMessage,
    GischatUncompliantMessage,
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
    """
    Returns list of available rooms
    :return: list of available rooms
    """
    return os.environ.get("ROOMS", "QGIS,Geotribu").split(",")


class WebsocketNotifier:
    """
    Class used to broadcast messages to registered websockets
    """

    # list of websockets connection associated to room
    connections: dict[str, list[WebSocket]]

    # list of user nicknames associated to their websocket
    users: dict[WebSocket, str]

    def __init__(self):
        # registered websockets for rooms
        self.connections: dict[str, list[WebSocket]] = {
            room: [] for room in available_rooms()
        }
        self.users = {}

    async def connect(self, room: str, websocket: WebSocket) -> None:
        """
        Connects a new user to a room
        :param room: room to connect the websocket to
        :param websocket: new user's websocket connection
        """
        await websocket.accept()
        self.connections[room].append(websocket)

    async def remove(self, room: str, websocket: WebSocket) -> None:
        """
        Removes a user from a room
        Should be called when a websocket is disconnected
        :param room: room to disconnect user from
        :param websocket: user's websocket connection
        """
        # remove websocket from connections
        if websocket in self.connections[room]:
            self.connections[room].remove(websocket)
        # unregister user
        if websocket in self.users.keys():
            exiter = self.users[websocket]
            del self.users[websocket]
            await self.notify_exiter(room, exiter)

    async def notify_room(self, room: str, message: GischatMessageModel) -> None:
        """
        Sends a message to a room
        :param room: room to notify
        :param message: message to send
        """
        living_connections = []
        while len(self.connections[room]) > 0:
            # Looping like this is necessary in case a disconnection is handled
            # during await websocket.send_json(message)
            websocket = self.connections[room].pop()
            try:
                await websocket.send_json(jsonable_encoder(message))
                living_connections.append(websocket)
            except WebSocketDisconnect:
                logger.error("Can not send message to disconnected websocket")
        self.connections[room] = living_connections

    def get_nb_connected_users(self, room: str) -> int:
        """
        Returns the number of connected users in a room
        :param room: room to check
        :return: number of connected users in a room
        """
        return len(self.connections[room])

    async def notify_nb_users(self, room: str) -> None:
        """
        Notifies connected users in a room with the number of connected users
        :param room: room to notify
        """
        message = GischatNbUsersMessage(nb_users=self.get_nb_connected_users(room))
        await self.notify_room(room, message)

    async def notify_newcomer(self, room: str, user: str) -> None:
        """
        Notifies a room that a newcomer has joined
        :param room: room to notify
        :param user: nickname of the newcomer
        """
        message = GischatNewcomerMessage(newcomer=user)
        await self.notify_room(room, message)

    async def notify_exiter(self, room: str, user: str) -> None:
        """
        Notifies a room that a user has left the room
        :param room: room to notify
        :param user: nickname of the exiter
        """
        message = GischatExiterMessage(exiter=user)
        await self.notify_room(room, message)

    def register_user(self, websocket: WebSocket, user: str) -> None:
        """
        Registers a user assigned to a websocket
        :param websocket: user's websocket
        :param user: user's nickname
        """
        self.users[websocket] = user

    def get_registered_users(self, room: str) -> list[str]:
        """
        Returns the nicknames of users registered in a room
        :param room: room to check
        :return: List of user names
        """
        users = []
        for ws in self.connections[room]:
            # use try/except instead of list comprehension
            # in case a user didn't register itself
            try:
                users.append(self.users[ws])
            except KeyError:
                continue
        return users

    def is_user_present(self, room: str, user: str) -> bool:
        """
        Checks if a user given by the nickname is registered in a room
        :param room: room to check
        :param user: user to check
        :return: True if present, False otherwise
        """
        for ws in self.connections[room]:
            try:
                if self.users[ws] == user:
                    return True
            except KeyError:
                continue
        return False

    async def notify_user(
        self, room: str, user: str, message: GischatMessageModel
    ) -> None:
        """
        Notifies a user in a room with a "private" message
        Private means only this user is notified of the message
        :param room: room
        :param user: user to notify
        :param message: message to send
        """
        for ws in self.connections[room]:
            try:
                if self.users[ws] == user:
                    try:
                        await ws.send_json(jsonable_encoder(message))
                    except WebSocketDisconnect:
                        logger.error("Can not send message to disconnected websocket")
            except KeyError:
                continue


notifier = WebsocketNotifier()


# initialize sentry
if "SENTRY_DSN" in os.environ and os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN"),
        environment=os.environ.get("ENVIRONMENT", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", 1)),
        profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", 1)),
    )


app = FastAPI(
    title="gischat API",
    summary="Chat with your GIS tribe in QGIS, GIS mobile apps and other clients !",
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


@app.get("/room/{room}/users")
async def get_connected_users(room: str) -> list[str]:
    if room not in notifier.connections.keys():
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")
    return sorted(notifier.get_registered_users(room), key=str.casefold)


@app.put(
    "/room/{room}/text",
    response_model=GischatTextMessage,
)
async def put_text_message(
    room: str, message: GischatTextMessage
) -> GischatTextMessage:
    if room not in notifier.connections.keys():
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")
    await notifier.notify_room(room, message)
    logger.info(f"Message in room '{room}': {message}")
    return message


@app.websocket("/room/{room}/ws")
async def websocket_endpoint(websocket: WebSocket, room: str) -> None:

    # check if room is registered
    if room not in notifier.connections.keys():
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")

    await notifier.connect(room, websocket)
    await notifier.notify_nb_users(room)
    logger.info(f"New websocket connected in room '{room}'")

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            try:
                message = GischatMessageModel(**payload)

                # text message
                if message.type == GischatMessageTypeEnum.TEXT:
                    message = GischatTextMessage(**payload)
                    logger.info(f"Message in room '{room}': {message}")
                    await notifier.notify_room(room, message)

                # image message
                if message.type == GischatMessageTypeEnum.IMAGE:
                    message = GischatImageMessage(**payload)
                    logger.info(f"Message (image) in room '{room}' by {message.author}")
                    # resize image if needed using MAX_IMAGE_SIZE env var
                    image = Image.open(BytesIO(base64.b64decode(message.image_data)))
                    size = int(os.environ.get("MAX_IMAGE_SIZE", 800))
                    image.thumbnail((size, size), Image.Resampling.LANCZOS)
                    img_byte_arr = BytesIO()
                    image.save(img_byte_arr, format="PNG")
                    message.image_data = base64.b64encode(
                        img_byte_arr.getvalue()
                    ).decode("utf-8")
                    await notifier.notify_room(room, message)

                # newcomer message
                if message.type == GischatMessageTypeEnum.NEWCOMER:
                    message = GischatNewcomerMessage(**payload)
                    notifier.register_user(websocket, message.newcomer)
                    logger.info(f"Newcomer in room {room}: {message.newcomer}")
                    await notifier.notify_newcomer(room, message.newcomer)

                # like message
                if message.type == GischatMessageTypeEnum.LIKE:
                    message = GischatLikeMessage(**payload)
                    logger.info(
                        f"{message.liker_author} liked {message.liked_author}'s message ({message.message})"
                    )
                    await notifier.notify_user(
                        room,
                        message.liked_author,
                        message,
                    )

                # geojson layer message
                if message.type == GischatMessageTypeEnum.GEOJSON:
                    message = GischatGeojsonLayerMessage(**payload)
                    # check if the number of features is compliant with the MAX_GEOJSON_FEATURES env variable
                    nb_features = len(message.geojson["features"])
                    max_nb_features = int(os.environ.get("MAX_GEOJSON_FEATURES", 500))
                    if nb_features > max_nb_features:
                        logger.error(
                            f"{message.author} sent a geojson layer ('{message.layer_name}') with too many features ({nb_features}"
                        )
                        # notify user with an uncompliant message
                        message = GischatUncompliantMessage(
                            reason=f"Too many geojson features : {nb_features} vs max {max_nb_features} allowed"
                        )
                        await websocket.send_json(jsonable_encoder(message))
                        continue
                    logger.info(
                        f"{message.author} sent a geojson layer ('{message.layer_name}'): {nb_features} features using crs '{message.crs_authid}'"
                    )
                    await notifier.notify_room(room, message)

            except ValidationError as e:
                logger.error(f"Uncompliant message: {e}")
                message = GischatUncompliantMessage(reason=str(e))
                await websocket.send_json(jsonable_encoder(message))

    except WebSocketDisconnect:
        await notifier.remove(room, websocket)
        await notifier.notify_nb_users(room)
        logger.info(f"Websocket disconnected from room '{room}'")
