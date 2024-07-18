import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from qchat_api.models import MessageModel, PostMessageModel


def get_conn_str():
    return f"""
    dbname={os.environ.get('POSTGRES_DB')}
    user={os.environ.get('POSTGRES_USER')}
    password={os.environ.get('POSTGRES_PASSWORD')}
    host={os.environ.get('POSTGRES_HOST')}
    port={os.environ.get('POSTGRES_PORT')}
    """


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.async_pool = AsyncConnectionPool(conninfo=get_conn_str())
    yield
    await app.async_pool.close()


async def insert_message(
    app: Any, room_name: str, message: PostMessageModel
) -> MessageModel:
    async with app.async_pool.connection() as conn:
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
