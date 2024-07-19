from datetime import datetime

from pydantic import BaseModel


class CreateRoomModel(BaseModel):
    name: str
    creator: str


class RoomModel(CreateRoomModel):
    name: str
    creator: str
    date_created: datetime = datetime.now()
    is_deletable: bool = True


class PostMessageModel(BaseModel):
    message: str
    author: str


class MessageModel(PostMessageModel):
    id: int
    date_posted: datetime = datetime.now()
    room: str
