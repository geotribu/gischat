# gischat - API

## Development

- Create local environment:

```sh
cp .env.example .env
```

- Launch API:

```sh
poetry run uvicorn gischat.app:app --reload --env-file .env
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
