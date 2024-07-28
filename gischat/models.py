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
        pattern=r"[a-z-A-Z-0-9-_]+",
    )
    avatar: Optional[str] = None

    def __str__(self) -> str:
        return f"[{self.author}]: '{self.message}'"

    def check_validity(self) -> tuple[bool, list[str]]:
        """
        Checks if a message is compliant with the rules.
        Rules:
        - author must be alphanumeric
        - author must have min length of 3
        - message length must be max 255
        :return: tuple with first element if message is ok,
        second element with errors if any
        """
        ok, errors = True, []

        # check alphanum author
        for c in self.author:
            if not c.isalnum() and c not in ["-", "_"]:
                ok = False
                errors.append(f"Character not alphanumeric found in author: {c}")

        return ok, errors


class MessageErrorModel(BaseModel):
    message: str
    errors: list[str]


class InternalMessageModel(BaseModel):
    author: str
    nb_users: int
