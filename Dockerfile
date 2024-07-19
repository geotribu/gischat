FROM python:3.10-alpine AS python-base
LABEL org.opencontainers.image.source="https://github.com/geotribu/gischat"
LABEL authors="Guilhem Allaman (contact@guilhemallaman.net)"

# Disable annoying pip version check, we don't care if pip is slightly older
ARG PIP_DISABLE_PIP_VERSION_CHECK 1

# Do not create and use redundant cache dir in the current user home
ARG PIP_NO_CACHE_DIR 1

WORKDIR /gischat

COPY ./pyproject.toml /gischat/pyproject.toml
COPY ./poetry.lock /gischat/poetry.lock

COPY gischat /gischat/gischat

RUN pip install poetry

RUN poetry install

CMD ["poetry", "run", "uvicorn", "gischat.app:app", "--proxy-headers", "--port", "8000", "--workers", "8"]
