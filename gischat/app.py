import json
import logging
import sys
from typing import Optional

import colorlog
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row
from starlette.websockets import WebSocketDisconnect

from gischat.constants import FETCH_MESSAGES_NUMBER
from gischat.db import insert_message, lifespan
from gischat.models import CreateRoomModel, MessageModel, PostMessageModel, RoomModel
from gischat.utils import get_version
from gischat.ws_html import ws_html

# logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = colorlog.ColoredFormatter(
    "%(yellow)s[%(asctime)s] %(log_color)s[%(levelname)s]%(reset)s %(purple)s[%(name)s %(module)s]%(reset)s %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)

app = FastAPI(
    title="gischat API",
    summary="Chat with your GIS tribe in QGIS, QField and other clients !",
    version=get_version(),
    lifespan=lifespan,
)


@app.get("/")
async def get_ws_page():
    return HTMLResponse(ws_html)


@app.get("/version")
async def get_version() -> dict:
    return {"version": get_version()}


@app.get("/status")
async def get_status(request: Request) -> dict:
    return {
        "status": "ok",
        "healthy": True,
        "db_pool": request.app.async_pool.get_stats(),
    }


@app.get("/rooms")
async def get_rooms(request: Request) -> list[RoomModel]:
    async with request.app.async_pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute("SELECT * FROM room ORDER BY date_created DESC")
            results = await cursor.fetchall()
            return [RoomModel(**r) for r in results]


@app.get("/room/{room_name}")
async def get_room_info(request: Request, room_name: str) -> Optional[RoomModel]:
    async with request.app.async_pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT *
                FROM room
                WHERE name LIKE %(name)s""",
                {"name": room_name},
            )
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=404, detail=f"Room with name '{room_name}' not found"
                )
            result = await cursor.fetchone()
            return RoomModel(**result)


@app.put("/room")
async def create_room(request: Request, room: CreateRoomModel) -> Optional[RoomModel]:
    async with request.app.async_pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
            INSERT INTO room (name, creator)
            VALUES (%(name)s, %(creator)s)
            RETURNING *""",
                {"name": room.name, "creator": room.creator},
            )
            result = await cursor.fetchone()
            return RoomModel(**result)


@app.get("/room/{room_name}/messages/{number}")
async def get_room_messages(
    request: Request, room_name: str, number: int = FETCH_MESSAGES_NUMBER
) -> list[MessageModel]:
    async with request.app.async_pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT *
                FROM message
                WHERE room LIKE %(room)s
                ORDER BY date_posted DESC
                LIMIT %(number)s
                """,
                {"room": room_name, "number": number},
            )
            results = await cursor.fetchall()
            return [MessageModel(**r) for r in results]


@app.put("/room/{room_name}/message")
async def put_message(
    request: Request, room_name: str, message: PostMessageModel
) -> MessageModel:
    async with request.app.async_pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
            INSERT INTO message (message, author, room)
            VALUES (%(message)s, %(author)s, %(room)s)
            RETURNING *""",
                {
                    "message": message.message,
                    "author": message.author,
                    "room": room_name,
                },
            )
            result = await cursor.fetchone()
            return MessageModel(**result)


@app.get("/messages/{number}")
async def get_latest_messages(
    request: Request, number: int = FETCH_MESSAGES_NUMBER
) -> list[MessageModel]:
    async with request.app.async_pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
            SELECT *
            FROM message
            ORDER BY date_posted DESC
            LIMIT %(number)s
            """,
                {"number": number},
            )
            results = await cursor.fetchall()
            return [MessageModel(**r) for r in results]


# region websocket


class Notifier:
    """
    Class used to broadcast messages to registered websockets
    """

    def __init__(self):
        # registered websockets for rooms
        self.connections: dict[str, list[WebSocket]] = {}
        self.generator = self.get_notification_generator()

    async def get_notification_generator(self):
        while True:
            room, message = yield
            await self.notify(room, message)

    async def push(self, msg: str):
        await self.generator.asend(msg)

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        if room not in self.connections.keys():
            self.connections[room] = []
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


notifier = Notifier()


@app.websocket("/room/{room_name}/ws")
async def websocket_endpoint(websocket: WebSocket, room_name: str):
    await notifier.connect(room_name, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            postmodel = PostMessageModel(**json.loads(data))
            logging.getLogger().info(f"WS message received: {postmodel}")
            pm = await insert_message(websocket.app, room_name, postmodel)
            await notifier.notify(room_name, json.dumps(jsonable_encoder(pm)))
    except WebSocketDisconnect:
        notifier.remove(room_name, websocket)


# endregion
