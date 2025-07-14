import os
import uuid

INSTANCE_ID = os.getenv("INSTANCE_ID", uuid.uuid4())
INSTANCE_CHANNELS = os.getenv("CHANNELS", "QGIS,Geotribu").split(",")

MAX_STORED_MESSAGES = int(os.getenv("MAX_STORED_MESSAGES", 5))

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"

MATRIX_ENABLED = os.getenv("MATRIX_ENABLED", "false").lower() in ("true", "1", "yes")
