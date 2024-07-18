FROM python:3.10-alpine AS python-base

RUN mkdir qchat
WORKDIR  /qchat

COPY /pyproject.toml /qchat
COPY . .

RUN pip install --no-cache-dir poetry
RUN poetry config virtualenvs.create false
RUN poetry install

CMD ["poetry", "run", "uvicorn", "qchat_api.app:app", "--workers", "8"]
