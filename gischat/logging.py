import logging
import sys

import colorlog

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = colorlog.ColoredFormatter(
    "%(yellow)s[%(asctime)s] %(log_color)s[%(levelname)s]%(reset)s %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)
