import asyncio
import base64
import json
import os
from contextlib import asynccontextmanager
from io import BytesIO
from uuid import UUID

import httpx
import redis.asyncio as redis
import sentry_sdk
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from PIL import Image
from pydantic import ValidationError
from redis import Redis as RedisObject
from starlette.websockets import WebSocketDisconnect

from gischat.dispatchers import (
    MatrixDispatcher,
    RedisDispatcher,
    forward_message_to_matrix_channel,
    get_redis_channel_key,
)
from gischat.env import (
    MATRIX_CHAT_ENABLED,
    MATRIX_PING_HOMESERVER,
    MATRIX_PING_MESSAGE_PREFIX,
    MATRIX_PING_ROOMID,
    MATRIX_PING_TOKEN,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_URL,
)
from gischat.logging import logger
from gischat.models import (
    ChannelStatusModel,
    MatrixRegisterRequest,
    MatrixRegisterResponse,
    QChatBboxMessage,
    QChatCrsMessage,
    QChatGeojsonLayerMessage,
    QChatImageMessage,
    QChatLikeMessage,
    QChatMessageModel,
    QChatMessageTypeEnum,
    QChatModelMessage,
    QChatNewcomerMessage,
    QChatPositionMessage,
    QChatTextMessage,
    QChatUncompliantMessage,
    QMatrixChatTextMessage,
    RulesModel,
    StatusModel,
    VersionModel,
)
from gischat.utils import QCHAT_CHEATCODES, get_uv_version

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

    redis_connection = RedisObject(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
    )

    redis_dispatcher.init_redis(
        pub=app.state.redis_pub, sub=app.state.redis_sub, connection=redis_connection
    )

    # register redis listener
    listener_task = asyncio.create_task(redis_listener(app))

    # let the app run
    yield

    # shutdown
    redis_dispatcher.clean()
    listener_task.cancel()
    await app.state.redis_pub.aclose()
    await app.state.redis_sub.aclose()
    redis_connection.close()
    logger.info("👋 Lifespan shutdown done.")


app = FastAPI(
    title="gischat API",
    summary="Chat with your GIS tribe in QGIS, GIS mobile apps and other clients !",
    version=get_uv_version(),
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="gischat/templates")


async def redis_listener(app: FastAPI) -> None:
    """
    Listens to redis pub/sub events and publishes messages to channel.
    :param app: FastAPI app.
    :param channel: name of the channel to list to.
    """

    pubsub = app.state.redis_sub.pubsub()
    redis_channel = get_redis_channel_key()

    await pubsub.subscribe(redis_channel)
    logger.info("✅ Redis listener running...")

    async for message in pubsub.listen():
        if message["type"] == "message":
            # extract the "channel" key to broadcast to the correct channel.
            message_data = json.loads(message["data"])
            channel = message_data.pop("channel")

            await redis_dispatcher.broadcast_to_active_websockets(
                channel, json.dumps(message_data)
            )


# region API endpoints


@app.get("/", response_class=HTMLResponse)
async def get_qchat_web_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="qchat.html",
    )


@app.get("/version", response_model=VersionModel)
async def get_version() -> VersionModel:
    return VersionModel(version=get_uv_version())


QFIELD_PLUGIN_LATEST_DOWNLOAD_URL = "https://github.com/geotribu/qchat-qfield-plugin/releases/latest/download/qfchat-latest.zip"


@app.get("/qfield")
async def get_latest_qfield_plugin() -> Response:
    async with httpx.AsyncClient() as client:
        remote_response = await client.get(
            QFIELD_PLUGIN_LATEST_DOWNLOAD_URL, follow_redirects=True
        )

        if remote_response.status_code != 200:
            return Response(
                content="Error while downloading latest QField plugin",
                status_code=remote_response.status_code,
            )

        return StreamingResponse(
            remote_response.aiter_bytes(),
            media_type=remote_response.headers.get(
                "content-type", "application/octet-stream"
            ),
            headers={"Content-Disposition": 'attachment; filename="qfchat-latest.zip"'},
        )


@app.get("/channels", response_model=list[str])
async def get_channels() -> list[str]:
    return redis_dispatcher.channels


@app.get("/status", response_model=StatusModel)
async def get_status() -> StatusModel:
    return StatusModel(
        status="ok",
        healthy=True,
        channels=[
            ChannelStatusModel(
                name=channel,
                nb_connected_users=redis_dispatcher.get_nb_connected_users(channel),
            )
            for channel in redis_dispatcher.channels
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


@app.get("/channel/{channel}/users")
async def get_connected_users(channel: str) -> list[str]:
    if channel not in redis_dispatcher.channels:
        raise HTTPException(
            status_code=404, detail=f"Channel '{channel}' not registered"
        )
    return sorted(redis_dispatcher.get_registered_users(channel), key=str.casefold)


@app.get("/channel/{channel}/last")
async def get_last_messages(channel: str) -> list:
    if channel not in redis_dispatcher.channels:
        raise HTTPException(
            status_code=404, detail=f"Channel '{channel}' not registered"
        )
    return redis_dispatcher.get_stored_messages(channel)


@app.put(
    "/channel/{channel}/text",
    response_model=QChatTextMessage,
)
async def put_text_message(channel: str, message: QChatTextMessage) -> QChatTextMessage:

    if channel not in redis_dispatcher.channels:
        raise HTTPException(
            status_code=404, detail=f"Channel '{channel}' not registered"
        )

    await redis_dispatcher.broadcast_to_redis_channel(channel, message)

    logger.info(f"Message in channel '{channel}': {message}")
    redis_dispatcher.store_message(channel, message)

    return message


# endregion


@app.websocket("/channel/{channel}/ws")
async def websocket_endpoint(websocket: WebSocket, channel: str) -> None:

    # check if channel is registered
    if channel not in redis_dispatcher.channels:
        # Policy Violation
        await websocket.close(code=1008, reason=f"Channel '{channel}' does not exist.")
        return

    await redis_dispatcher.accept_websocket(channel, websocket)
    logger.info(f"🤝 New websocket client joined channel {channel}")

    redis_dispatcher.increment_nb_connected_users(channel)
    await redis_dispatcher.notify_nb_users(channel)

    # send channel's last stored message
    for message in redis_dispatcher.get_stored_messages(channel):
        await websocket.send_json(jsonable_encoder(message))

    try:
        while True:
            payload = await websocket.receive_json()

            try:
                message = QChatMessageModel(**payload)

                # text message
                if message.type == QChatMessageTypeEnum.TEXT:
                    message = QChatTextMessage(**payload)

                    logger.info(f"💬 [{channel}]: ({message.author}): '{message.text}'")
                    await redis_dispatcher.broadcast_to_redis_channel(channel, message)

                    if message.text not in QCHAT_CHEATCODES:
                        redis_dispatcher.store_message(channel, message)

                    if (
                        message.text.startswith(MATRIX_PING_MESSAGE_PREFIX)
                        and MATRIX_PING_MESSAGE_PREFIX
                        and MATRIX_PING_HOMESERVER
                        and MATRIX_PING_ROOMID
                        and MATRIX_PING_TOKEN
                    ):
                        logger.info(
                            f"🏓 [{channel}]: Matrix ping received, forwarding to Matrix channel."
                        )
                        await forward_message_to_matrix_channel(message, channel)

                # image message
                if message.type == QChatMessageTypeEnum.IMAGE:
                    message = QChatImageMessage(**payload)

                    # resize image if needed using MAX_IMAGE_SIZE env var
                    image = Image.open(BytesIO(base64.b64decode(message.image_data)))
                    size = int(os.environ.get("MAX_IMAGE_SIZE", 800))
                    image.thumbnail((size, size), Image.Resampling.LANCZOS)
                    img_byte_arr = BytesIO()
                    image.save(img_byte_arr, format="PNG")
                    message.image_data = base64.b64encode(
                        img_byte_arr.getvalue()
                    ).decode("utf-8")

                    logger.info(f"🖼️ [{channel}]: ({message.author}): shared an image")
                    await redis_dispatcher.broadcast_to_redis_channel(channel, message)

                    redis_dispatcher.store_message(channel, message)

                # newcomer message
                if message.type == QChatMessageTypeEnum.NEWCOMER:
                    message = QChatNewcomerMessage(**payload)

                    # check if user is already registered
                    if redis_dispatcher.is_user_present(channel, message.newcomer):
                        logger.info(
                            f"❌ User '{message.newcomer}' wants to register but there is already a '{message.newcomer}' in channel {channel}"
                        )
                        message = QChatUncompliantMessage(
                            reason=f"User '{message.newcomer}' already registered in channel {channel}"
                        )
                        await websocket.send_json(jsonable_encoder(message))
                        continue
                    redis_dispatcher.register_user(channel, websocket, message.newcomer)

                    logger.info(f"🤝 [{channel}]: Welcome to {message.newcomer} !")
                    await redis_dispatcher.notify_newcomer(channel, message.newcomer)

                # like message
                if message.type == QChatMessageTypeEnum.LIKE:
                    message = QChatLikeMessage(**payload)

                    logger.info(
                        f"👍 [{channel}]: {message.liker_author} liked {message.liked_author}'s message ({message.message})"
                    )
                    await redis_dispatcher.broadcast_to_redis_channel(channel, message)

                # geojson layer message
                if message.type == QChatMessageTypeEnum.GEOJSON:
                    message = QChatGeojsonLayerMessage(**payload)

                    # check if the number of features is compliant
                    # must not be greater than the MAX_GEOJSON_FEATURES env variable
                    nb_features = len(message.geojson["features"])
                    max_nb_features = int(os.environ.get("MAX_GEOJSON_FEATURES", 500))
                    if nb_features > max_nb_features:
                        logger.error(
                            f"❌ {message.author} sent a geojson layer ('{message.layer_name}') with too many features ({nb_features}"
                        )
                        # notify user with an uncompliant message
                        message = QChatUncompliantMessage(
                            reason=f"Too many geojson features : {nb_features} vs max {max_nb_features} allowed"
                        )
                        await websocket.send_json(jsonable_encoder(message))
                        continue

                    logger.info(
                        f"🌍 [{channel}]: ({message.author}): shared geojson layer '{message.layer_name}' ({nb_features} features, crs: '{message.crs_authid}')"
                    )
                    await redis_dispatcher.broadcast_to_redis_channel(channel, message)

                    redis_dispatcher.store_message(channel, message)

                # crs message
                if message.type == QChatMessageTypeEnum.CRS:
                    message = QChatCrsMessage(**payload)

                    logger.info(
                        f"📐 [{channel}]: ({message.author}): shared crs '{message.crs_authid}'"
                    )
                    await redis_dispatcher.broadcast_to_redis_channel(channel, message)

                    redis_dispatcher.store_message(channel, message)

                # bbox message
                if message.type == QChatMessageTypeEnum.BBOX:
                    message = QChatBboxMessage(**payload)

                    logger.info(
                        f"🔳 [{channel}]: ({message.author}): shared bbox using crs '{message.crs_authid}'"
                    )
                    await redis_dispatcher.broadcast_to_redis_channel(channel, message)

                    redis_dispatcher.store_message(channel, message)

                # position message
                if message.type == QChatMessageTypeEnum.POSITION:
                    message = QChatPositionMessage(**payload)

                    logger.info(
                        f"📍 [{channel}]: ({message.author}): shared position '{message.x} x {message.y}' using crs '{message.crs_authid}'"
                    )
                    await redis_dispatcher.broadcast_to_redis_channel(channel, message)

                    redis_dispatcher.store_message(channel, message)

                # graphic model message
                if message.type == QChatMessageTypeEnum.MODEL:
                    message = QChatModelMessage(**payload)

                    logger.info(
                        f"🧮 [{channel}]: ({message.author}): shared graphic model '{message.model_name}'"
                    )
                    await redis_dispatcher.broadcast_to_redis_channel(channel, message)

                    redis_dispatcher.store_message(channel, message)

            except ValidationError as e:
                message = QChatUncompliantMessage(reason=str(e))

                logger.error(f"❌ Uncompliant message shared: {e}")
                await redis_dispatcher.broadcast_to_redis_channel(channel, message)

    except WebSocketDisconnect:

        logger.info(f"❌ Websocket client disconnected from {channel}")
        redis_dispatcher.remove_websocket(channel, websocket)

        redis_dispatcher.decrement_nb_connected_users(channel)
        await redis_dispatcher.notify_nb_users(channel)


# region matrix

matrix_dispatcher = MatrixDispatcher.instance()


if MATRIX_CHAT_ENABLED:

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
                    message = QChatMessageModel(**payload)

                    # text message
                    if message.type == QChatMessageTypeEnum.TEXT:
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
                    message = QChatUncompliantMessage(reason=str(e))
                    logger.error(f"❌ Uncompliant message shared: {e}")
                    await websocket.send_json(jsonable_encoder(message))

        except WebSocketDisconnect:

            logger.info("❌ Matrix websocket client disconnected.")
            await matrix_dispatcher.remove_websocket(request_id, websocket)


# endregion
