import asyncio
import base64
import os
from contextlib import asynccontextmanager
from io import BytesIO
from uuid import UUID

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

from gischat.dispatchers import (
    MatrixDispatcher,
    RedisDispatcher,
    get_redis_channel_key,
)
from gischat.env import (
    INSTANCE_ROOMS,
    MATRIX_ENABLED,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_URL,
)
from gischat.logging import logger
from gischat.models import (
    GischatBboxMessage,
    GischatCrsMessage,
    GischatGeojsonLayerMessage,
    GischatImageMessage,
    GischatLikeMessage,
    GischatMessageModel,
    GischatMessageTypeEnum,
    GischatModelMessage,
    GischatNewcomerMessage,
    GischatPositionMessage,
    GischatTextMessage,
    GischatUncompliantMessage,
    MatrixRegisterRequest,
    MatrixRegisterResponse,
    QMatrixChatTextMessage,
    RoomStatusModel,
    RulesModel,
    StatusModel,
    VersionModel,
)
from gischat.utils import QCHAT_CHEATCODES, get_poetry_version

# initialize sentry
if os.getenv("SENTRY_DSN", None):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        environment=os.getenv("ENVIRONMENT", "production"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", 1)),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", 1)),
    )


redis_dispatcher = RedisDispatcher.instance()


@asynccontextmanager
async def lifespan(app: FastAPI):

    # startup
    logger.info("🚀 Starting lifespan, connecting to Redis...")
    app.state.redis_pub = await redis.from_url(REDIS_URL, decode_responses=True)
    app.state.redis_sub = await redis.from_url(REDIS_URL, decode_responses=True)

    redis_dispatcher.init_redis(
        pub=app.state.redis_pub,
        sub=app.state.redis_sub,
        connection=RedisObject(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
        ),
    )

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
    await app.state.redis_pub.aclose()
    await app.state.redis_sub.aclose()
    logger.info("👋 Lifespan shutdown done.")


app = FastAPI(
    title="gischat API",
    summary="Chat with your GIS tribe in QGIS, GIS mobile apps and other clients !",
    version=get_poetry_version(),
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="gischat/templates")


async def redis_listener(app: FastAPI, room: str) -> None:
    """
    Listens to redis pub/sub events and publishes messages to room.
    :param app: FastAPI app.
    :param room: name of the room to list to.
    """

    pubsub = app.state.redis_sub.pubsub()
    redis_channel = get_redis_channel_key(room)

    await pubsub.subscribe(redis_channel)
    logger.info(f"✅ Redis listener running for room {room}")

    async for message in pubsub.listen():
        if message["type"] == "message":
            await redis_dispatcher.broadcast_to_active_websockets(room, message["data"])


# region API endpoints


@app.get("/", response_class=HTMLResponse)
async def get_ws_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="qchat.html",
    )


@app.get("/version", response_model=VersionModel)
async def get_version() -> VersionModel:
    return VersionModel(version=get_poetry_version())


@app.get("/rooms", response_model=list[str])
async def get_rooms() -> list[str]:
    return redis_dispatcher.rooms


@app.get("/status", response_model=StatusModel)
async def get_status() -> StatusModel:
    return StatusModel(
        status="ok",
        healthy=True,
        rooms=[
            RoomStatusModel(
                name=room,
                nb_connected_users=redis_dispatcher.get_nb_connected_users(room),
            )
            for room in redis_dispatcher.rooms
        ],
    )


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
    if room not in redis_dispatcher.rooms:
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")
    return sorted(redis_dispatcher.get_registered_users(room), key=str.casefold)


@app.get("/room/{room}/last")
async def get_last_messages(room: str) -> list:
    if room not in redis_dispatcher.rooms:
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")
    return redis_dispatcher.get_stored_messages(room)


@app.put(
    "/room/{room}/text",
    response_model=GischatTextMessage,
)
async def put_text_message(
    room: str, message: GischatTextMessage
) -> GischatTextMessage:

    if room not in redis_dispatcher.rooms:
        raise HTTPException(status_code=404, detail=f"Room '{room}' not registered")

    await redis_dispatcher.broadcast_to_redis_channel(room, message)

    logger.info(f"Message in room '{room}': {message}")
    redis_dispatcher.store_message(room, message)

    return message


# endregion


@app.websocket("/room/{room}/ws")
async def websocket_endpoint(websocket: WebSocket, room: str) -> None:

    # check if room is registered
    if room not in redis_dispatcher.rooms:
        # Policy Violation
        await websocket.close(code=1008, reason=f"Room '{room}' does not exist.")
        return

    await redis_dispatcher.accept_websocket(room, websocket)
    logger.info(f"🤝 New websocket client joined room {room}")

    redis_dispatcher.increment_nb_connected_users(room)
    await redis_dispatcher.notify_nb_users(room)

    # send room's last stored message
    for message in redis_dispatcher.get_stored_messages(room):
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
                    await redis_dispatcher.broadcast_to_redis_channel(room, message)

                    if message.text not in QCHAT_CHEATCODES:
                        redis_dispatcher.store_message(room, message)

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
                    await redis_dispatcher.broadcast_to_redis_channel(room, message)

                    redis_dispatcher.store_message(room, message)

                # newcomer message
                if message.type == GischatMessageTypeEnum.NEWCOMER:
                    message = GischatNewcomerMessage(**payload)

                    # check if user is already registered
                    if redis_dispatcher.is_user_present(room, message.newcomer):
                        logger.info(
                            f"❌ User '{message.newcomer}' wants to register but there is already a '{message.newcomer}' in room {room}"
                        )
                        message = GischatUncompliantMessage(
                            reason=f"User '{message.newcomer}' already registered in room {room}"
                        )
                        await websocket.send_json(jsonable_encoder(message))
                        continue
                    redis_dispatcher.register_user(room, websocket, message.newcomer)

                    logger.info(f"🤝 [{room}]: Welcome to {message.newcomer} !")
                    await redis_dispatcher.notify_newcomer(room, message.newcomer)

                # like message
                if message.type == GischatMessageTypeEnum.LIKE:
                    message = GischatLikeMessage(**payload)

                    logger.info(
                        f"👍 [{room}]: {message.liker_author} liked {message.liked_author}'s message ({message.message})"
                    )
                    await redis_dispatcher.broadcast_to_redis_channel(room, message)

                # geojson layer message
                if message.type == GischatMessageTypeEnum.GEOJSON:
                    message = GischatGeojsonLayerMessage(**payload)

                    # check if the number of features is compliant
                    # must not be greater than the MAX_GEOJSON_FEATURES env variable
                    nb_features = len(message.geojson["features"])
                    max_nb_features = int(os.environ.get("MAX_GEOJSON_FEATURES", 500))
                    if nb_features > max_nb_features:
                        logger.error(
                            f"❌ {message.author} sent a geojson layer ('{message.layer_name}') with too many features ({nb_features}"
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
                    await redis_dispatcher.broadcast_to_redis_channel(room, message)

                    redis_dispatcher.store_message(room, message)

                # crs message
                if message.type == GischatMessageTypeEnum.CRS:
                    message = GischatCrsMessage(**payload)

                    logger.info(
                        f"📐 [{room}]: ({message.author}): shared crs '{message.crs_authid}'"
                    )
                    await redis_dispatcher.broadcast_to_redis_channel(room, message)

                    redis_dispatcher.store_message(room, message)

                # bbox message
                if message.type == GischatMessageTypeEnum.BBOX:
                    message = GischatBboxMessage(**payload)

                    logger.info(
                        f"🔳 [{room}]: ({message.author}): shared bbox using crs '{message.crs_authid}'"
                    )
                    await redis_dispatcher.broadcast_to_redis_channel(room, message)

                    redis_dispatcher.store_message(room, message)

                # position message
                if message.type == GischatMessageTypeEnum.POSITION:
                    message = GischatPositionMessage(**payload)

                    logger.info(
                        f"📍 [{room}]: ({message.author}): shared position '{message.x} x {message.y}' using crs '{message.crs_authid}'"
                    )
                    await redis_dispatcher.broadcast_to_redis_channel(room, message)

                    redis_dispatcher.store_message(room, message)

                # graphic model message
                if message.type == GischatMessageTypeEnum.MODEL:
                    message = GischatModelMessage(**payload)

                    logger.info(
                        f"🧮 [{room}]: ({message.author}): shared graphic model '{message.model_name}'"
                    )
                    await redis_dispatcher.broadcast_to_redis_channel(room, message)

                    redis_dispatcher.store_message(room, message)

            except ValidationError as e:
                message = GischatUncompliantMessage(reason=str(e))

                logger.error(f"❌ Uncompliant message shared: {e}")
                await redis_dispatcher.broadcast_to_redis_channel(room, message)

    except WebSocketDisconnect:

        logger.info(f"❌ Websocket client disconnected from {room}")
        redis_dispatcher.remove_websocket(room, websocket)

        redis_dispatcher.decrement_nb_connected_users(room)
        await redis_dispatcher.notify_nb_users(room)


# region matrix

matrix_dispatcher = MatrixDispatcher.instance()


if MATRIX_ENABLED:

    @app.get("/matrix", response_class=HTMLResponse)
    async def get_matrix_ws_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="qmatrixchat.html",
        )

    @app.post(
        "/matrix/register",
        response_model=MatrixRegisterResponse,
    )
    async def post_matrix_registration_request(
        body: MatrixRegisterRequest,
    ) -> MatrixRegisterResponse:
        request_id = matrix_dispatcher.register_request(body)
        logger.info("🧑‍💻 Matrix registration request received.")
        return MatrixRegisterResponse(request_id=request_id)

    @app.websocket("/matrix/{request_id}/ws")
    async def matrix_websocket_endpoint(websocket: WebSocket, request_id: UUID) -> None:

        # check if request is registered.
        if not matrix_dispatcher.has_registered_request(request_id):
            # Policy Violation
            await websocket.close(
                code=1008, reason=f"Request '{request_id}' is not registered."
            )
            return

        try:
            async_client = await matrix_dispatcher.accept_websocket(
                request_id, websocket
            )
        except Exception as e:
            logger.error(f"❌ Error while accepting Matrix websocket: {e}")
            await websocket.close(
                code=1000, reason=f"Error while accepting websocket: {e}"
            )
            return

        room_id = matrix_dispatcher.get_registration_request_room_id(request_id)

        await async_client.sync(timeout=30000)

        try:
            while True:
                payload = await websocket.receive_json()

                try:
                    message = GischatMessageModel(**payload)

                    # text message
                    if message.type == GischatMessageTypeEnum.TEXT:
                        print("payload: ", payload)
                        message = QMatrixChatTextMessage(**payload)

                        logger.info(
                            f"💬 [matrix]: ({message.author}): '{message.text}'"
                        )
                        await async_client.room_send(
                            room_id=room_id,
                            message_type="m.room.message",
                            content={"msgtype": "m.text", "body": message.text},
                        )

                except ValidationError as e:
                    message = GischatUncompliantMessage(reason=str(e))
                    logger.error(f"❌ Uncompliant message shared: {e}")
                    await websocket.send_json(jsonable_encoder(message))

        except WebSocketDisconnect:

            logger.info("❌ Matrix websocket client disconnected.")
            await matrix_dispatcher.remove_websocket(request_id, websocket)


# endregion
