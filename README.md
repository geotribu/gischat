# gischat - API

## Development

- Create local environment:

```sh
cp .env.example .env
```

- Run local database:

```sh
source .env
docker compose up db
```

- Launch API:

```sh
poetry run uvicorn gischat.app:app --reload --env-file .env
```
