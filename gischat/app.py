import asyncio
import base64
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from io import BytesIO

import colorlog
import redis.asyncio as redis
import sentry_sdk
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from PIL import Image
from pydantic import ValidationError
from redis import Redis as RedisObject
from starlette.websockets import WebSocketDisconnect

from gischat.models import (
    GischatBboxMessage,
    GischatCrsMessage,
    GischatExiterMessage,
    GischatGeojsonLayerMessage,
    GischatImageMessage,
    GischatLikeMessage,
    GischatMessageModel,
    GischatMessageTypeEnum,
    GischatModelMessage,
    GischatNbUsersMessage,
    GischatNewcomerMessage,
    GischatPositionMessage,
    GischatTextMessage,
    GischatUncompliantMessage,
    RulesModel,
    VersionModel,
    parse_gischat_message,
)
from gischat.utils import QCHAT_CHEATCODES, get_poetry_version

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


INSTANCE_ID = os.getenv("INSTANCE_ID", uuid.uuid4())
INSTANCE_ROOMS = os.getenv("ROOMS", "QGIS,Geotribu").split(",")

MAX_STORED_MESSAGES = int(os.getenv("MAX_STORED_MESSAGES", 5))

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"

redis_connection = RedisObject(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
)


class WebsocketNotifier:
    """
    Class used to broadcast messages to registered websockets
    """

    _instance = None

    @classmethod
    def instance(cls) -> "WebsocketNotifier":
        if cls._instance is None:
            cls._instance = WebsocketNotifier(INSTANCE_ROOMS)
        return cls._instance

    # list of websockets connection associated to room
    connections: dict[str, list[WebSocket]]

    # list of user nicknames associated to their websocket
    users: dict[WebSocket, str]

    # store last sent messages in lists
    last_messages: dict[str, list[GischatMessageModel]]

    def __init__(self, rooms: list[str]):
        self.rooms = rooms
        # registered websockets for rooms
        self.connections: dict[str, list[WebSocket]] = {room: [] for room in rooms}
        self.users = {}
        self.last_messages = {room: [] for room in rooms}

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

    def _room_storage_key(self, room: str) -> str:
        """
        Returns a key for the room name.
        Typically used for redis cache.
        :param room: room name
        :return: storage key for the room
        """
        return f"iid:{INSTANCE_ID};room:{room};messages"

    def store_message(self, room: str, message: GischatMessageModel) -> None:
        """
        Stores a message sent in a room
        Will keep only the last MAX_STORED_MESSAGES (env var)
        :param room: room to store the message
        :param message: message to store
        """
        storage_key = self._room_storage_key(room)
        text_value = message.model_dump_json()

        redis_connection.lpush(storage_key, text_value)
        redis_connection.ltrim(storage_key, 0, MAX_STORED_MESSAGES - 1)

    def get_stored_messages(self, room: str) -> list[GischatMessageModel]:
        """
        Returns the last messages sent and stored in a room
        :param room: room with stored messages
        :return: list of last messages sent and stored in the room
        """
        storage_key = self._room_storage_key(room)
        raw_stored = redis_connection.lrange(storage_key, 0, -1)

        messages = []
        for raw in reversed(raw_stored):
            message = parse_gischat_message(json.loads(raw))

            messages.append(message)

        return messages

    def clear_stored_messages(self) -> None:
        """
        Clears the stored messages
        """
        for room in self.rooms:
            redis_connection.delete(self._room_storage_key(room))


# initialize sentry
if os.getenv("SENTRY_DSN", None):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        environment=os.getenv("ENVIRONMENT", "production"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", 1)),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", 1)),
    )

active_connections = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    logger.info("🚀 Starting lifespan, connecting to Redis...")
    app.state.redis_pub = await redis.from_url(REDIS_URL, decode_responses=True)
    app.state.redis_sub = await redis.from_url(REDIS_URL, decode_responses=True)

    # register room listeners
    app.state.listener_tasks = []
    for room in INSTANCE_ROOMS:
        listener_task = asyncio.create_task(redis_listener(app, room))
        app.state.listener_tasks.append(listener_task)

    # let the app run
    yield

    # shutdown
    for listener_task in app.state.listener_tasks:
        listener_task.cancel()
    await app.state.redis_pub.close()
    await app.state.redis_sub.close()
    logger.info("👋 Lifespan shutdown done.")


app = FastAPI(
    title="gischat API",
    summary="Chat with your GIS tribe in QGIS, GIS mobile apps and other clients !",
    version=get_poetry_version(),
    lifespan=lifespan,
)
templates = Jinja2Templates(directory="gischat/templates")


def get_redis_channel(room: str) -> str:
    return f"{INSTANCE_ID}_{room}"


async def redis_listener(app: FastAPI, room: str) -> None:
    """
    Listens to redis pub/sub events and publishes messages to room.
    :param app: FastAPI app.
    :param room: name of the room to list to.
    """

    pubsub = app.state.redis_sub.pubsub()
    redis_channel = get_redis_channel(room)
    await pubsub.subscribe(redis_channel)
    logger.info(f"✅ Listener running for room: {room} ({redis_channel})")

    async for message in pubsub.listen():
        if message["type"] == "message":
            await broadcast(room, message["data"])


async def broadcast(room: str, message: str) -> None:
    """
    Broadcast a message to a rooms.
    :param room: room to broadcast the message to.
    :param message: message to broadcast.
    """
    connections = active_connections.get(room, [])
    for ws in connections:
        try:
            await ws.send_text(message)
        except Exception as e:
            logger.error(f"❌ Error sending message to {ws}: {e}")
            connections.remove(ws)


# region API endpoints


@app.get("/", response_class=HTMLResponse)
async def get_ws_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="ws-page.html",
    )


@app.get("/version", response_model=VersionModel)
async def get_version() -> VersionModel:
    return VersionModel(version=get_poetry_version())


@app.get("/rooms", response_model=list[str])
async def get_rooms() -> list[str]:
    return WebsocketNotifier.instance().rooms


@app.get("/rules", response_model=RulesModel)
async def get_rules() -> RulesModel:
    return RulesModel(
        rules=os.environ.get("RULES", "YOLO"),
        main_lang=os.environ.get("MAIN_LANG", "en"),
        min_author_length=int(os.environ.get("MIN_AUTHOR_LENGTH", 3)),
        max_author_length=int(os.environ.get("MAX_AUTHOR_LENGTH", 32)),
        max_message_length=int(os.environ.get("MAX_MESSAGE_LENGTH", 255)),
        max_image_size=int(os.environ.get("MAX_IMAGE_SIZE", 800)),
        max_geojson_features=int(os.environ.get("MAX_GEOJSON_FEATURES", 500)),
    )


@app.get("/room/{room}/users")
async def get_connected_users(room: str) -> list[str]:
    notifier = WebsocketNotifier.instance()
    if room not in notifier.rooms:
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")
    return sorted(notifier.get_registered_users(room), key=str.casefold)


@app.get("/room/{room}/last")
async def get_last_messages(room: str) -> list:
    notifier = WebsocketNotifier.instance()
    if room not in notifier.rooms:
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")
    return notifier.get_stored_messages(room)


@app.put(
    "/room/{room}/text",
    response_model=GischatTextMessage,
)
async def put_text_message(
    room: str, message: GischatTextMessage
) -> GischatTextMessage:
    notifier = WebsocketNotifier.instance()
    if room not in notifier.rooms:
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")
    await notifier.notify_room(room, message)
    logger.info(f"Message in room '{room}': {message}")
    notifier.store_message(room, message)
    return message


# endregion


@app.websocket("/room/{room}/ws")
async def websocket_endpoint(websocket: WebSocket, room: str) -> None:

    # check if the room is registered.
    if room not in INSTANCE_ROOMS:
        await websocket.close(
            code=1008, reason=f"Room '{room}' does not exist."
        )  # Policy Violation
        return

    notifier = WebsocketNotifier.instance()

    # check if room is registered
    if room not in notifier.rooms:
        await websocket.close(
            code=1008, reason=f"Room '{room}' does not exist."
        )  # Policy Violation
        return

    await websocket.accept()
    active_connections.setdefault(room, []).append(websocket)
    logger.info(f"🧑‍🚀 New websocket client joined room {room}")

    # id of the redis channel
    redis_channel = get_redis_channel(room)

    # send room's last stored message
    for message in notifier.get_stored_messages(room):
        await websocket.send_json(jsonable_encoder(message))

    try:
        while True:
            payload = await websocket.receive_json()

            try:
                message = GischatMessageModel(**payload)

                # text message
                if message.type == GischatMessageTypeEnum.TEXT:
                    message = GischatTextMessage(**payload)

                    logger.info(f"💬 [{room}]: ({message.author}): '{message.text}'")
                    await app.state.redis_pub.publish(
                        redis_channel, message.model_dump_json()
                    )

                    if message.text not in QCHAT_CHEATCODES:
                        notifier.store_message(room, message)

                # image message
                if message.type == GischatMessageTypeEnum.IMAGE:
                    message = GischatImageMessage(**payload)

                    # resize image if needed using MAX_IMAGE_SIZE env var
                    image = Image.open(BytesIO(base64.b64decode(message.image_data)))
                    size = int(os.environ.get("MAX_IMAGE_SIZE", 800))
                    image.thumbnail((size, size), Image.Resampling.LANCZOS)
                    img_byte_arr = BytesIO()
                    image.save(img_byte_arr, format="PNG")
                    message.image_data = base64.b64encode(
                        img_byte_arr.getvalue()
                    ).decode("utf-8")

                    logger.info(f"🖼️ [{room}]: ({message.author}): shared an image")
                    await app.state.redis_pub.publish(
                        redis_channel, message.model_dump_json()
                    )

                    notifier.store_message(room, message)

                # newcomer message
                if message.type == GischatMessageTypeEnum.NEWCOMER:
                    message = GischatNewcomerMessage(**payload)

                    logger.info(f"🤝 [{room}]: Welcome to {message.newcomer} !")
                    await app.state.redis_pub.publish(
                        redis_channel, message.model_dump_json()
                    )

                # like message
                if message.type == GischatMessageTypeEnum.LIKE:
                    message = GischatLikeMessage(**payload)

                    logger.info(
                        f"🤝 [{room}]: {message.liker_author} liked {message.liked_author}'s message ({message.message})"
                    )
                    await app.state.redis_pub.publish(
                        redis_channel, message.model_dump_json()
                    )

                # geojson layer message
                if message.type == GischatMessageTypeEnum.GEOJSON:
                    message = GischatGeojsonLayerMessage(**payload)

                    # check if the number of features is compliant
                    # must not be greater than the MAX_GEOJSON_FEATURES env variable
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
                        f"🌍 [{room}]: ({message.author}): shared geojson layer '{message.layer_name}' ({nb_features} features, crs: '{message.crs_authid}')"
                    )
                    await app.state.redis_pub.publish(
                        redis_channel, message.model_dump_json()
                    )

                    notifier.store_message(room, message)

                # crs message
                if message.type == GischatMessageTypeEnum.CRS:
                    message = GischatCrsMessage(**payload)

                    logger.info(
                        f"📐 [{room}]: ({message.author}): shared crs '{message.crs_authid}'"
                    )
                    await app.state.redis_pub.publish(
                        redis_channel, message.model_dump_json()
                    )

                    notifier.store_message(room, message)

                # bbox message
                if message.type == GischatMessageTypeEnum.BBOX:
                    message = GischatBboxMessage(**payload)

                    logger.info(
                        f"🔳 [{room}]: ({message.author}): shared bbox using crs '{message.crs_authid}'"
                    )
                    await app.state.redis_pub.publish(
                        redis_channel, message.model_dump_json()
                    )

                    notifier.store_message(room, message)

                # position message
                if message.type == GischatMessageTypeEnum.POSITION:
                    message = GischatPositionMessage(**payload)

                    logger.info(
                        f"📍 [{room}]: ({message.author}): shared position '{message.x} x {message.y}' using crs '{message.crs_authid}'"
                    )
                    await app.state.redis_pub.publish(
                        redis_channel, message.model_dump_json()
                    )

                    notifier.store_message(room, message)

                # graphic model message
                if message.type == GischatMessageTypeEnum.MODEL:
                    message = GischatModelMessage(**payload)
                    logger.info(
                        f"🧮 [{room}]: ({message.author}): shared graphic model '{message.model_name}'"
                    )
                    await notifier.notify_room(room, message)
                    notifier.store_message(room, message)

            except ValidationError as e:
                message = GischatUncompliantMessage(reason=str(e))

                logger.error(f"❌ Uncompliant message shared: {e}")
                await app.state.redis_pub.publish(
                    redis_channel, message.model_dump_json()
                )

    except WebSocketDisconnect:
        await notifier.notify_nb_users(room)

        active_connections[room].remove(websocket)
        logger.info(f"❌ Websocket client disconnected from {room}")
