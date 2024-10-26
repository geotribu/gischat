import os
from enum import Enum
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


GISCHAT_NICKNAME_FIELD = Field(
    min_length=int(os.environ.get("MIN_AUTHOR_LENGTH", 3)),
    max_length=int(os.environ.get("MAX_AUTHOR_LENGTH", 32)),
    pattern=r"^[a-z-A-Z-0-9-_]+$",
)
GISCHAT_TEXT_MESSAGE_FIELD = Field(
    max_length=int(os.environ.get("MAX_MESSAGE_LENGTH", 255))
)


class GischatMessageTypeEnum(Enum):
    TEXT = "text"
    IMAGE = "image"
    NB_USERS = "nb_users"
    NEWCOMER = "newcomer"
    EXITER = "exiter"
    LIKE = "like"

    def __str__(self) -> str:
        return self.value


class GischatMessageModel(BaseModel):
    type: GischatMessageTypeEnum = Field(frozen=True, description="Type of message")


class GischatTextMessage(GischatMessageModel):
    type: GischatMessageTypeEnum = GischatMessageTypeEnum.TEXT
    author: str = GISCHAT_NICKNAME_FIELD
    avatar: Optional[str] = Field(default=None)
    text: str = GISCHAT_TEXT_MESSAGE_FIELD

    def __str__(self) -> str:
        return f"[{self.author}]: '{self.text}'"


class GischatImageMessage(GischatMessageModel):
    type: GischatMessageTypeEnum = GischatMessageTypeEnum.IMAGE
    author: str = GISCHAT_NICKNAME_FIELD
    avatar: Optional[str] = Field(default=None)
    image_data: str = Field(description="String of the encoded image")


class GischatNbUsersMessage(GischatMessageModel):
    type: GischatMessageTypeEnum = GischatMessageTypeEnum.NB_USERS
    nb_users: int = Field(description="Number of users in the room")


class GischatNewcomerMessage(GischatMessageModel):
    type: GischatMessageTypeEnum = GischatMessageTypeEnum.NEWCOMER
    newcomer: str = GISCHAT_NICKNAME_FIELD


class GischatExiterMessage(GischatMessageModel):
    type: GischatMessageTypeEnum = GischatMessageTypeEnum.EXITER
    exiter: str = GISCHAT_NICKNAME_FIELD


class GischatLikeMessage(GischatMessageModel):
    type: GischatMessageTypeEnum = GischatMessageTypeEnum.LIKE
    liker_author: str = GISCHAT_NICKNAME_FIELD
    liked_author: str = GISCHAT_NICKNAME_FIELD
    message: str = GISCHAT_TEXT_MESSAGE_FIELD
