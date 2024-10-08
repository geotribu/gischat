import os
from typing import Optional

from pydantic import BaseModel, Field


class VersionModel(BaseModel):
    version: str


class RoomStatusModel(BaseModel):
    name: str
    nb_connected_users: int


class StatusModel(BaseModel):
    status: str
    healthy: bool
    rooms: list[RoomStatusModel]


class RulesModel(BaseModel):
    rules: str
    main_lang: str
    min_author_length: int
    max_author_length: int
    max_message_length: int


class MessageModel(BaseModel):
    message: str = Field(
        None, max_length=int(os.environ.get("MAX_MESSAGE_LENGTH", 255))
    )
    author: str = Field(
        None,
        min_length=int(os.environ.get("MIN_AUTHOR_LENGTH", 3)),
        max_length=int(os.environ.get("MAX_AUTHOR_LENGTH", 32)),
        pattern=r"^[a-z-A-Z-0-9-_]+$",
    )
    avatar: Optional[str] = None

    def __str__(self) -> str:
        return f"[{self.author}]: '{self.message}'"


class InternalNbUsersMessageModel(BaseModel):
    author: str
    nb_users: int


class InternalNewcomerMessageModel(BaseModel):
    author: str
    newcomer: str = Field(
        None,
        min_length=int(os.environ.get("MIN_AUTHOR_LENGTH", 3)),
        max_length=int(os.environ.get("MAX_AUTHOR_LENGTH", 32)),
        pattern=r"^[a-z-A-Z-0-9-_]+$",
    )
