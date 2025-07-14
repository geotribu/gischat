import json
from functools import partial
from uuid import UUID, uuid4

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from nio import AsyncClient, MatrixRoom, RoomMessageText
from redis import Redis as RedisObject
from starlette.websockets import WebSocketDisconnect

from gischat.env import (
    INSTANCE_CHANNELS,
    INSTANCE_ID,
    MAX_STORED_MESSAGES,
    REDIS_HOST,
    REDIS_PORT,
)
from gischat.logging import logger
from gischat.models import (
    MatrixRegisterRequest,
    QChatExiterMessage,
    QChatMessageModel,
    QChatNbUsersMessage,
    QChatNewcomerMessage,
    QMatrixChatTextMessage,
    parse_qchat_message,
)


def get_redis_channel_key(channel: str) -> str:
    return f"iid:{INSTANCE_ID};channel:{channel}"


def get_redis_last_messages_key(channel: str) -> str:
    return f"iid:{INSTANCE_ID};channel:{channel};last_messages"


def get_redis_nb_users_key(channel: str) -> str:
    return f"iid:{INSTANCE_ID};channel:{channel};nb_users"


def get_redis_users_key(channel: str) -> str:
    return f"iid:{INSTANCE_ID};channel:{channel};registered_users"


class RedisDispatcher:

    # singleton implementation
    _instance = None

    @classmethod
    def instance(cls) -> "RedisDispatcher":
        if cls._instance is None:
            cls._instance = RedisDispatcher(INSTANCE_CHANNELS)
        return cls._instance

    # redis PubSub clients
    redis_pub: RedisObject
    redis_sub: RedisObject
    redis_connection: RedisObject

    # list of websockets connections associated to channel
    active_connections: dict[str, list[WebSocket]]

    # list of websockets connections associated to user
    users_websockets: dict[str, dict[WebSocket, str]]

    def __init__(self, channels: list[str]):
        self.channels = channels
        self.active_connections = {}
        self.users_websockets = {}

        for channel in channels:
            self.active_connections[channel] = []
            self.users_websockets[channel] = {}

    def init_redis(
        self, pub: RedisObject, sub: RedisObject, connection: RedisObject
    ) -> None:
        self.redis_pub = pub
        self.redis_sub = sub
        self.redis_connection = connection

    async def accept_websocket(self, channel: str, websocket: WebSocket) -> None:
        """
        Connects a new user to a channel.
        :param channel: channel to connect the websocket to.
        :param websocket: new user's websocket connection.
        """
        await websocket.accept()
        self.active_connections[channel].append(websocket)

    def remove_websocket(self, channel: str, websocket: WebSocket) -> None:
        """
        Removes a websocket from a channel.
        Should be called when a websocket is disconnected.
        :param channel: channel to disconnect user from.
        :param websocket: user's websocket connection.
        """
        # remove websocket from connections.
        if websocket in self.active_connections[channel]:
            self.active_connections[channel].remove(websocket)

        # remove connected user if registered.
        if websocket in self.users_websockets[channel]:
            user = self.users_websockets[channel][websocket]
            self.users_websockets[channel].pop(websocket)
            self.redis_connection.lrem(get_redis_users_key(channel), 0, user)

    async def broadcast_to_active_websockets(self, channel: str, message: str) -> None:
        """
        Broadcasts a message coming from redis to active websockets in a channel.
        :param channel: channel to notify.
        :param message: message to broadcast.
        """
        active_connections = self.active_connections.get(channel, [])
        for ws in active_connections:
            try:
                await ws.send_text(message)
            except WebSocketDisconnect as e:
                logger.error(f"❌ Error sending message to {ws}: {e}")
                active_connections.remove(ws)

    async def broadcast_to_redis_channel(
        self, channel: str, message: QChatMessageModel
    ) -> None:
        await self.redis_pub.publish(
            get_redis_channel_key(channel), message.model_dump_json()
        )

    def get_nb_connected_users(self, channel: str) -> int:
        nb_users_redis_key = get_redis_nb_users_key(channel)

        if not self.redis_connection.exists(nb_users_redis_key):
            self.redis_connection.set(nb_users_redis_key, 0)

        return self.redis_connection.get(nb_users_redis_key)

    def increment_nb_connected_users(self, channel: str) -> int:
        return self.redis_connection.incr(get_redis_nb_users_key(channel))

    def decrement_nb_connected_users(self, channel: str) -> int:
        return self.redis_connection.decr(get_redis_nb_users_key(channel))

    async def notify_nb_users(self, channel: str) -> None:
        """
        Notifies connected users in a channel with the number of connected users.
        :param channel: channel to notify.
        """
        message = QChatNbUsersMessage(nb_users=self.get_nb_connected_users(channel))
        await self.broadcast_to_redis_channel(channel, message)

    async def notify_newcomer(self, channel: str, user: str) -> None:
        """
        Notifies a channel that a newcomer has joined.
        :param channel: channel to notify.
        :param user: nickname of the newcomer.
        """
        message = QChatNewcomerMessage(newcomer=user)
        await self.broadcast_to_redis_channel(channel, message)

    async def notify_exiter(self, channel: str, user: str) -> None:
        """
        Notifies a channel that a user has left the channel.
        :param channel: channel to notify.
        :param user: nickname of the exiter.
        """
        message = QChatExiterMessage(exiter=user)
        await self.broadcast_to_redis_channel(channel, message)

    def register_user(self, channel: str, websocket: WebSocket, user: str) -> None:
        """
        Registers a user assigned to a websocket.
        :param websocket: user's websocket.
        :param user: user's nickname.
        """
        self.redis_connection.rpush(get_redis_users_key(channel), user)
        self.users_websockets[channel][websocket] = user

    def get_registered_users(self, channel: str) -> list[str]:
        """
        Returns the nicknames of users registered in a channel.
        :param channel: channel to check.
        :return: List of user names.
        """
        return self.redis_connection.lrange(get_redis_users_key(channel), 0, -1)

    def is_user_present(self, channel: str, user: str) -> bool:
        """
        Checks if a user given by the nickname is registered in a channel.
        :param channel: channel to check.
        :param user: user to check.
        :return: True if present, False otherwise.
        """
        users_list = self.get_registered_users(channel)
        return user in users_list

    async def notify_user(
        self, channel: str, user: str, message: QChatMessageModel
    ) -> None:
        """
        Notifies a user in a channel with a "private" message.
        Private means only this user is notified of the message.
        :param channel: channel to notify.
        :param user: user to notify.
        :param message: message to send.
        """
        for ws in self.active_connections[channel]:
            try:
                if self.users[ws] == user:
                    try:
                        await ws.send_json(jsonable_encoder(message))
                    except WebSocketDisconnect:
                        logger.error("Can not send message to disconnected websocket")
            except KeyError:
                continue

    def store_message(self, channel: str, message: QChatMessageModel) -> None:
        """
        Stores a message sent in a channel.
        Will keep only the last MAX_STORED_MESSAGES (env var).
        :param channel: channel to store the message.
        :param message: message to store.
        """
        last_message_key = get_redis_last_messages_key(channel)
        text_value = message.model_dump_json()

        self.redis_connection.lpush(last_message_key, text_value)
        self.redis_connection.ltrim(last_message_key, 0, MAX_STORED_MESSAGES - 1)

    def get_stored_messages(self, channel: str) -> list[QChatMessageModel]:
        """
        Returns the last messages sent and stored in a channel.
        :param channel: channel with stored messages.
        :return: list of last messages sent and stored in the channel.
        """
        last_message_key = get_redis_last_messages_key(channel)
        raw_stored = self.redis_connection.lrange(last_message_key, 0, -1)

        messages = []
        for raw in reversed(raw_stored):
            message = parse_qchat_message(json.loads(raw))
            messages.append(message)

        return messages


def get_redis_matrix_registrations_key(uuid: UUID) -> str:
    return f"iid:{INSTANCE_ID};req:{uuid};matrix_registrations"


class MatrixDispatcher:

    # singleton implementation
    _instance = None

    @classmethod
    def instance(cls) -> "MatrixDispatcher":
        if cls._instance is None:
            cls._instance = MatrixDispatcher()
        return cls._instance

    websocket_uuids: dict[UUID, WebSocket]
    websocket_connections: dict[WebSocket, AsyncClient]

    redis: RedisObject

    def __init__(self):
        self.registrations = {}
        self.websocket_uuids = {}
        self.websocket_connections = {}

        self.redis = RedisObject(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
        )

    def register_request(self, body: MatrixRegisterRequest) -> UUID:
        """
        Registers a new Matrix registration request.
        :param body: Body of the registration request.
        :return: UUID of the registration request.
        """
        uuid = uuid4()
        mapping = body.model_dump()
        print(mapping)
        self.redis.hset(get_redis_matrix_registrations_key(uuid), mapping=mapping)
        return uuid

    def has_registered_request(self, uuid: UUID) -> bool:
        """
        Checks if a registration request with the given UUID exists.
        :param uuid: UUID of the registration request.
        :return: True if the request exists, False otherwise.
        """
        return self.redis.exists(get_redis_matrix_registrations_key(uuid)) > 0

    def get_registration_request(self, request_id: UUID) -> MatrixRegisterRequest:
        """
        Returns the registration request associated with a UUID.
        :param request_id: UUID of the registration request.
        :return: MatrixRegisterRequest object.
        """
        if not self.has_registered_request(request_id):
            raise ValueError(f"Request {request_id} is not registered.")

        mapping = self.redis.hgetall(get_redis_matrix_registrations_key(request_id))
        return MatrixRegisterRequest(**mapping)

    def get_registration_request_room_id(self, request_id: UUID) -> str:
        """
        Returns the channel ID associated with a registration request.
        :param request_id: UUID of the registration request.
        :return: Channel ID of the registration request.
        """
        return self.get_registration_request(request_id).room_id

    async def accept_websocket(
        self, request_id: UUID, websocket: WebSocket
    ) -> AsyncClient:
        """
        Accepts a websocket connection for a Matrix registration request.
        :param websocket: WebSocket connection to accept.
        :param request_id: UUID of the registration request.
        """
        await websocket.accept()

        self.websocket_uuids[request_id] = websocket

        matrix_registration = self.get_registration_request(request_id)

        client = AsyncClient(
            homeserver=matrix_registration.homeserver,
            user=matrix_registration.user,
        )

        login_result = await client.login(matrix_registration.password)
        logger.info(f"🧑‍💻 Matrix client logged in: {login_result}")

        client.add_event_callback(
            partial(self.on_matrix_text_message_received, websocket=websocket),
            RoomMessageText,
        )

        self.websocket_connections[websocket] = client

        return client

    async def remove_websocket(self, request_id: UUID, websocket: WebSocket) -> None:
        """
        Removes a websocket connection for a Matrix registration request.
        :param request_id: UUID of the registration request.
        :param websocket: WebSocket connection to remove.
        """
        self.redis.hdel(get_redis_matrix_registrations_key(request_id), str(request_id))
        self.websocket_uuids.pop(request_id, None)
        client = self.websocket_connections.pop(websocket, None)

        if not client:
            return

        await client.close()

    async def on_matrix_text_message_received(
        self, room: MatrixRoom, event: RoomMessageText, websocket: WebSocket
    ) -> None:
        """
        Callback for when a text message is received in a Matrix room.
        :param room: Matrix room where the message was received.
        :param event: Event containing the message.
        """
        if not isinstance(event, RoomMessageText):
            return

        message = QMatrixChatTextMessage(
            author=room.user_name(event.sender),
            text=event.body,
        )

        await websocket.send_json(jsonable_encoder(message))
