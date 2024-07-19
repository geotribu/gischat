FROM python:3.10-alpine AS python-base
LABEL org.opencontainers.image.source="https://github.com/geotribu/qchat-api"
LABEL authors="Guilhem Allaman (contact@guilhemallaman.net)"

# Disable annoying pip version check, we don't care if pip is slightly older
ARG PIP_DISABLE_PIP_VERSION_CHECK 1

# Do not create and use redundant cache dir in the current user home
ARG PIP_NO_CACHE_DIR 1

WORKDIR /qchat

COPY ./pyproject.toml /qchat/pyproject.toml
COPY ./poetry.lock /qchat/poetry.lock

COPY ./qchat_api /qchat/qchat_api

RUN pip install poetry

RUN poetry install

CMD ["poetry", "run", "uvicorn", "qchat_api.app:app", "--proxy-headers", "--port", "8000", "--workers", "8"]
