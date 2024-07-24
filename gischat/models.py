from pydantic import BaseModel


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


class MessageModel(BaseModel):
    message: str
    author: str

    def __str__(self) -> str:
        return f"[{self.author}]: '{self.message}'"


class InternalMessageModel(BaseModel):
    author: str
    nb_users: int
