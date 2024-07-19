from pydantic import BaseModel


class MessageModel(BaseModel):
    message: str
    author: str

    def __str__(self) -> str:
        return f"[{self.author}]: '{self.message}'"
