# Gischat - API

Gischat API backend for chatting with your tribe in GIS tools like QGIS, QField and many other to come

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![flake8](https://img.shields.io/badge/linter-flake8-green)](https://flake8.pycqa.org/)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

[![🐍 Linter](https://github.com/geotribu/gischat/actions/workflows/lint.yml/badge.svg)](https://github.com/geotribu/gischat/actions/workflows/lint.yml)
[![⚒️ Deploy docker image](https://github.com/geotribu/gischat/actions/workflows/docker.yml/badge.svg)](https://github.com/geotribu/gischat/actions/workflows/docker.yml)

[![Docker Pulls](https://badgen.net/docker/pulls/gounux/gischat?icon=docker&label=pulls)](https://hub.docker.com/r/gounux/gischat/)
[![Docker Stars](https://badgen.net/docker/stars/gounux/gischat?icon=docker&label=stars)](https://hub.docker.com/r/gounux/gischat/)
[![Docker Image Size](https://badgen.net/docker/size/gounux/gischat?icon=docker&label=image%20size)](https://hub.docker.com/r/gounux/gischat/)

![Github stars](https://badgen.net/github/stars/geotribu/gischat?icon=github&label=stars)
![Github forks](https://badgen.net/github/forks/geotribu/gischat?icon=github&label=forks)
![Github issues](https://img.shields.io/github/issues/geotribu/gischat)
![Github last-commit](https://img.shields.io/github/last-commit/geotribu/gischat)

## Development

- Install [poetry](https://python-poetry.org/):

```sh
python -m pip install poetry
```

- Install project's dependencies using poetry:

```sh
poetry install
```

- Install pre-commit tools:

```sh
poetry run pre-commit install
```

- Create local environment file:

```sh
cp .env.example .env
```

- Launch API:

```sh
poetry run uvicorn gischat.app:app --reload --env-file .env --log-config=log_config.yaml
```

## Build

- Build docker image:

```sh
docker build . --tag geotribu/gischat:latest
```

- Run docker image:

```sh
docker run geotribu/latest --env ROOMS=QGIS,QField,Geotribu
```
