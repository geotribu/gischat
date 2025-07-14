import datetime
import os
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError


class VersionModel(BaseModel):
    version: str


class ChannelStatusModel(BaseModel):
    name: str
    nb_connected_users: int


class StatusModel(BaseModel):
    status: str
    healthy: bool
    channels: list[ChannelStatusModel]


class RulesModel(BaseModel):
    rules: str
    main_lang: str
    min_author_length: int
    max_author_length: int
    max_message_length: int
    max_image_size: int
    max_geojson_features: int


QCHAT_NICKNAME_FIELD = Field(
    min_length=int(os.environ.get("MIN_AUTHOR_LENGTH", 3)),
    max_length=int(os.environ.get("MAX_AUTHOR_LENGTH", 32)),
    pattern=r"^[a-z-A-Z-0-9-_]+$",
)
QCHAT_TEXT_MESSAGE_FIELD = Field(
    max_length=int(os.environ.get("MAX_MESSAGE_LENGTH", 255))
)

CRS_WKT_FIELD = Field(description="WKT string of the CRS")
CRS_AUTHID_FIELD = Field(description="Auth id of the crs, e.g.: 'EPSG:4326'")


class QChatMessageTypeEnum(Enum):
    UNCOMPLIANT = "uncompliant"
    TEXT = "text"
    IMAGE = "image"
    NB_USERS = "nb_users"
    NEWCOMER = "newcomer"
    EXITER = "exiter"
    LIKE = "like"
    GEOJSON = "geojson"
    CRS = "crs"
    BBOX = "bbox"
    POSITION = "position"
    MODEL = "model"

    def __str__(self) -> str:
        return self.value


class QChatMessageModel(BaseModel):
    type: QChatMessageTypeEnum = Field(frozen=True, description="Type of message")
    id: UUID = Field(
        description="Unique identifier of the message", default_factory=uuid4
    )
    timestamp: int = Field(
        description="Timestamp of the message in seconds since epoch",
        default_factory=lambda: int(datetime.datetime.now().timestamp()),
    )


class QChatUncompliantMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.UNCOMPLIANT
    reason: str = Field(description="Reason of the uncompliant message")


class QChatTextMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.TEXT
    author: str = QCHAT_NICKNAME_FIELD
    avatar: Optional[str] = Field(default=None)
    text: str = QCHAT_TEXT_MESSAGE_FIELD

    def __str__(self) -> str:
        return f"[{self.author}]: '{self.text}'"


class QChatImageMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.IMAGE
    author: str = QCHAT_NICKNAME_FIELD
    avatar: Optional[str] = Field(default=None)
    image_data: str = Field(description="String of the encoded image")


class QChatNbUsersMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.NB_USERS
    nb_users: int = Field(description="Number of users in the channel")


class QChatNewcomerMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.NEWCOMER
    newcomer: str = QCHAT_NICKNAME_FIELD


class QChatExiterMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.EXITER
    exiter: str = QCHAT_NICKNAME_FIELD


class QChatLikeMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.LIKE
    liker_author: str = QCHAT_NICKNAME_FIELD
    liked_author: str = QCHAT_NICKNAME_FIELD
    message: str = QCHAT_TEXT_MESSAGE_FIELD


class QChatGeojsonLayerMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.GEOJSON
    author: str = QCHAT_NICKNAME_FIELD
    avatar: Optional[str] = Field(default=None)
    layer_name: str = Field(description="Name of the layer")
    crs_wkt: str = CRS_WKT_FIELD
    crs_authid: str = CRS_AUTHID_FIELD
    geojson: dict = Field(description="Geo data as geojson")
    style: Optional[str] = Field(
        default=None, description="QML style of the layer (AllStyleCategories)"
    )


class QChatCrsMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.CRS
    author: str = QCHAT_NICKNAME_FIELD
    avatar: Optional[str] = Field(default=None)
    crs_wkt: str = CRS_WKT_FIELD
    crs_authid: str = CRS_AUTHID_FIELD


class QChatBboxMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.BBOX
    author: str = QCHAT_NICKNAME_FIELD
    avatar: Optional[str] = Field(default=None)
    crs_wkt: str = CRS_WKT_FIELD
    crs_authid: str = CRS_AUTHID_FIELD
    xmin: float
    xmax: float
    ymin: float
    ymax: float


class QChatPositionMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.POSITION
    author: str = QCHAT_NICKNAME_FIELD
    avatar: Optional[str] = Field(default=None)
    crs_wkt: str = CRS_WKT_FIELD
    crs_authid: str = CRS_AUTHID_FIELD
    x: float
    y: float


class QChatModelMessage(QChatMessageModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.MODEL
    author: str = QCHAT_NICKNAME_FIELD
    avatar: Optional[str] = Field(default=None)
    model_name: str = Field(description="Name of the QGIS graphic model")
    model_group: Optional[str] = Field(
        default=None, description="Group of the QGIS graphic model"
    )
    raw_xml: str = Field(description="Raw XML of the QGIS graphic model")


def build_message_type_mapping(
    base_cls: type[QChatMessageModel],
) -> dict[QChatMessageTypeEnum, type[QChatMessageModel]]:
    mapping = {}
    for subclass in base_cls.__subclasses__():
        fields = getattr(subclass, "model_fields", {})
        type_field = fields.get("type")
        if type_field is None:
            continue

        default = type_field.default
        if isinstance(default, QChatMessageTypeEnum):
            mapping[default] = subclass
    return mapping


message_type_mapping = build_message_type_mapping(QChatMessageModel)


def parse_qchat_message(data: dict[str, Any]) -> QChatMessageModel:
    """
    Gischat message factory.
    """
    if "type" not in data:
        return QChatUncompliantMessage(reason="Missing 'type' field")

    try:
        msg_type = QChatMessageTypeEnum(data["type"])
    except ValueError:
        return QChatUncompliantMessage(reason=f"Unknown type: {data['type']}")

    cls = message_type_mapping.get(msg_type, QChatMessageModel)

    try:
        return cls(**data)
    except ValidationError as e:
        return QChatUncompliantMessage(reason=f"Validation error: {e}")


class MatrixRegisterRequest(BaseModel):
    homeserver: str = Field(
        description="Matrix home server URL, e.g. 'https://matrix.example.com'"
    )
    room_id: str = Field(
        description="ID of the room to join on the Matrix server",
    )
    user: str = Field(
        description="Username to register on the Matrix server",
    )
    password: str = Field(
        description="Password to register on the Matrix server",
    )
    device_id: str = Field(
        description="Device ID to register on the Matrix server. If not provided, a random one will be generated.",
        default_factory=lambda: uuid4().hex,
    )


class MatrixRegisterResponse(BaseModel):
    request_id: UUID = Field(
        description="UUID of the registration request", default_factory=uuid4
    )


class QMatrixChatTextMessage(BaseModel):
    type: QChatMessageTypeEnum = QChatMessageTypeEnum.TEXT
    id: UUID = Field(
        description="Unique identifier of the message", default_factory=uuid4
    )
    timestamp: int = Field(
        description="Timestamp of the message in seconds since epoch",
        default_factory=lambda: int(datetime.datetime.now().timestamp()),
    )
    author: str = Field(
        description="Author of the message, usually a Matrix user ID, e.g. '@user:example.com'",
    )
    text: str = Field(
        description="Text content of the message",
    )
