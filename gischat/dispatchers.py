import json
from functools import partial
from uuid import UUID, uuid4

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from nio import AsyncClient, MatrixRoom, RoomMessageText
from redis import Redis as RedisObject
from starlette.websockets import WebSocketDisconnect

from gischat.env import (
    INSTANCE_ID,
    INSTANCE_ROOMS,
    MAX_STORED_MESSAGES,
    REDIS_HOST,
    REDIS_PORT,
)
from gischat.logging import logger
from gischat.models import (
    GischatExiterMessage,
    GischatMessageModel,
    GischatNbUsersMessage,
    GischatNewcomerMessage,
    MatrixRegisterRequest,
    QMatrixChatTextMessage,
    parse_gischat_message,
)


def get_redis_channel_key(room: str) -> str:
    return f"iid:{INSTANCE_ID};room:{room}"


def get_redis_last_messages_key(room: str) -> str:
    return f"iid:{INSTANCE_ID};room:{room};last_messages"


def get_redis_nb_users_key(room: str) -> str:
    return f"iid:{INSTANCE_ID};room:{room};nb_users"


def get_redis_users_key(room: str) -> str:
    return f"iid:{INSTANCE_ID};room:{room};registered_users"


class RedisDispatcher:

    # singleton implementation
    _instance = None

    @classmethod
    def instance(cls) -> "RedisDispatcher":
        if cls._instance is None:
            cls._instance = RedisDispatcher(INSTANCE_ROOMS)
        return cls._instance

    # redis PubSub clients
    redis_pub: RedisObject
    redis_sub: RedisObject
    redis_connection: RedisObject

    # list of websockets connections associated to room
    active_connections: dict[str, list[WebSocket]]

    # list of websockets connections associated to user
    users_websockets: dict[str, dict[WebSocket, str]]

    def __init__(self, rooms: list[str]):
        self.rooms = rooms
        self.active_connections = {}
        self.users_websockets = {}

        for room in rooms:
            self.active_connections[room] = []
            self.users_websockets[room] = {}

    def init_redis(
        self, pub: RedisObject, sub: RedisObject, connection: RedisObject
    ) -> None:
        self.redis_pub = pub
        self.redis_sub = sub
        self.redis_connection = connection

    async def accept_websocket(self, room: str, websocket: WebSocket) -> None:
        """
        Connects a new user to a room.
        :param room: room to connect the websocket to.
        :param websocket: new user's websocket connection.
        """
        await websocket.accept()
        self.active_connections[room].append(websocket)

    def remove_websocket(self, room: str, websocket: WebSocket) -> None:
        """
        Removes a websocket from a room.
        Should be called when a websocket is disconnected.
        :param room: room to disconnect user from.
        :param websocket: user's websocket connection.
        """
        # remove websocket from connections.
        if websocket in self.active_connections[room]:
            self.active_connections[room].remove(websocket)

        # remove connected user if registered.
        if websocket in self.users_websockets[room]:
            user = self.users_websockets[room][websocket]
            self.users_websockets[room].pop(websocket)
            self.redis_connection.lrem(get_redis_users_key(room), 0, user)

    async def broadcast_to_active_websockets(self, room: str, message: str) -> None:
        """
        Broadcasts a message coming from redis to active websockets in a room.
        :param room: room to notify.
        :param message: message to broadcast.
        """
        active_connections = self.active_connections.get(room, [])
        for ws in active_connections:
            try:
                await ws.send_text(message)
            except WebSocketDisconnect as e:
                logger.error(f"❌ Error sending message to {ws}: {e}")
                active_connections.remove(ws)

    async def broadcast_to_redis_channel(
        self, room: str, message: GischatMessageModel
    ) -> None:
        await self.redis_pub.publish(
            get_redis_channel_key(room), message.model_dump_json()
        )

    def get_nb_connected_users(self, room: str) -> int:
        nb_users_redis_key = get_redis_nb_users_key(room)

        if not self.redis_connection.exists(nb_users_redis_key):
            self.redis_connection.set(nb_users_redis_key, 0)

        return self.redis_connection.get(nb_users_redis_key)

    def increment_nb_connected_users(self, room: str) -> int:
        return self.redis_connection.incr(get_redis_nb_users_key(room))

    def decrement_nb_connected_users(self, room: str) -> int:
        return self.redis_connection.decr(get_redis_nb_users_key(room))

    async def notify_nb_users(self, room: str) -> None:
        """
        Notifies connected users in a room with the number of connected users.
        :param room: room to notify.
        """
        message = GischatNbUsersMessage(nb_users=self.get_nb_connected_users(room))
        await self.broadcast_to_redis_channel(room, message)

    async def notify_newcomer(self, room: str, user: str) -> None:
        """
        Notifies a room that a newcomer has joined.
        :param room: room to notify.
        :param user: nickname of the newcomer.
        """
        message = GischatNewcomerMessage(newcomer=user)
        await self.broadcast_to_redis_channel(room, message)

    async def notify_exiter(self, room: str, user: str) -> None:
        """
        Notifies a room that a user has left the room.
        :param room: room to notify.
        :param user: nickname of the exiter.
        """
        message = GischatExiterMessage(exiter=user)
        await self.broadcast_to_redis_channel(room, message)

    def register_user(self, room: str, websocket: WebSocket, user: str) -> None:
        """
        Registers a user assigned to a websocket.
        :param websocket: user's websocket.
        :param user: user's nickname.
        """
        self.redis_connection.rpush(get_redis_users_key(room), user)
        self.users_websockets[room][websocket] = user

    def get_registered_users(self, room: str) -> list[str]:
        """
        Returns the nicknames of users registered in a room.
        :param room: room to check.
        :return: List of user names.
        """
        return self.redis_connection.lrange(get_redis_users_key(room), 0, -1)

    def is_user_present(self, room: str, user: str) -> bool:
        """
        Checks if a user given by the nickname is registered in a room.
        :param room: room to check.
        :param user: user to check.
        :return: True if present, False otherwise.
        """
        users_list = self.get_registered_users(room)
        return user in users_list

    async def notify_user(
        self, room: str, user: str, message: GischatMessageModel
    ) -> None:
        """
        Notifies a user in a room with a "private" message.
        Private means only this user is notified of the message.
        :param room: room.
        :param user: user to notify.
        :param message: message to send.
        """
        for ws in self.active_connections[room]:
            try:
                if self.users[ws] == user:
                    try:
                        await ws.send_json(jsonable_encoder(message))
                    except WebSocketDisconnect:
                        logger.error("Can not send message to disconnected websocket")
            except KeyError:
                continue

    def store_message(self, room: str, message: GischatMessageModel) -> None:
        """
        Stores a message sent in a room.
        Will keep only the last MAX_STORED_MESSAGES (env var).
        :param room: room to store the message.
        :param message: message to store.
        """
        last_message_key = get_redis_last_messages_key(room)
        text_value = message.model_dump_json()

        self.redis_connection.lpush(last_message_key, text_value)
        self.redis_connection.ltrim(last_message_key, 0, MAX_STORED_MESSAGES - 1)

    def get_stored_messages(self, room: str) -> list[GischatMessageModel]:
        """
        Returns the last messages sent and stored in a room.
        :param room: room with stored messages.
        :return: list of last messages sent and stored in the room.
        """
        last_message_key = get_redis_last_messages_key(room)
        raw_stored = self.redis_connection.lrange(last_message_key, 0, -1)

        messages = []
        for raw in reversed(raw_stored):
            message = parse_gischat_message(json.loads(raw))
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
        Returns the room ID associated with a registration request.
        :param request_id: UUID of the registration request.
        :return: Room ID of the registration request.
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
