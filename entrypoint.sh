#! /bin/sh

WORKERS=${NB_UVICORN_WORKERS:-1}

exec uv run uvicorn gischat.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --log-config=log_config.yaml \
    --workers $WORKERS
