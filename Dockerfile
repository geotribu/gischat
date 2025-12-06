FROM python:3.12-alpine AS python-base
LABEL org.opencontainers.image.source="https://github.com/geotribu/gischat"
LABEL maintainer="Guilhem Allaman <contact@guilhemallaman.net>"

# Disable annoying pip version check, we don't care if pip is slightly older
ARG PIP_DISABLE_PIP_VERSION_CHECK 1

# Do not create and use redundant cache dir in the current user home
ARG PIP_NO_CACHE_DIR 1

WORKDIR /gischat

COPY pyproject.toml /gischat/pyproject.toml
COPY uv.lock /gischat/uv.lock
COPY log_config.yaml /gischat/log_config.yaml
COPY entrypoint.sh /gischat/entrypoint.sh
COPY README.md /gischat/README.md

COPY gischat /gischat/gischat

RUN chmod +x entrypoint.sh \
&& pip install uv

RUN uv sync

EXPOSE 8000

CMD ["./entrypoint.sh"]
