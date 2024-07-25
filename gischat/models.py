import os

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

        # check author min length
        min_author_length = int(os.environ.get("MIN_AUTHOR_LENGTH", 3))
        if len(self.author) < min_author_length:
            ok = False
            errors.append(f"Author must have at least {min_author_length} characters")

        # check author max length
        max_author_length = int(os.environ.get("MAX_AUTHOR_LENGTH", 32))
        if len(self.author) > max_author_length:
            ok = False
            errors.append(f"Author too long: max {max_author_length} characters")

        # check message max length
        max_message_length = int(os.environ.get("MAX_MESSAGE_LENGTH", 255))
        if len(self.message) > max_message_length:
            ok = False
            errors.append(f"Message too long: max {max_message_length} characters")

        return ok, errors


class MessageErrorModel(BaseModel):
    message: str
    errors: list[str]


class InternalMessageModel(BaseModel):
    author: str
    nb_users: int
