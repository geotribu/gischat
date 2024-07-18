# QChat - API

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
poetry run uvicorn qchat_api.app:app --reload --env-file .env
```
