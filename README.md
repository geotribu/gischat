# Gischat - API

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![flake8](https://img.shields.io/badge/linter-flake8-green)](https://flake8.pycqa.org/)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/geotribu/gischat/main.svg)](https://results.pre-commit.ci/latest/github/geotribu/gischat/main)

[![🎳 Tester](https://github.com/geotribu/gischat/actions/workflows/tests.yml/badge.svg)](https://github.com/geotribu/gischat/actions/workflows/tests.yml)
[![🐍 Linter](https://github.com/geotribu/gischat/actions/workflows/lint.yml/badge.svg)](https://github.com/geotribu/gischat/actions/workflows/lint.yml)
[![⚒️ Deploy docker image](https://github.com/geotribu/gischat/actions/workflows/docker.yml/badge.svg)](https://github.com/geotribu/gischat/actions/workflows/docker.yml)
[![codecov](https://codecov.io/github/geotribu/gischat/graph/badge.svg?token=EW5SU9VKRD)](https://codecov.io/github/geotribu/gischat)

[![Docker Pulls](https://badgen.net/docker/pulls/gounux/gischat?icon=docker&label=pulls)](https://hub.docker.com/r/gounux/gischat/)
[![Docker Stars](https://badgen.net/docker/stars/gounux/gischat?icon=docker&label=stars)](https://hub.docker.com/r/gounux/gischat/)
[![Docker Image Size](https://badgen.net/docker/size/gounux/gischat?icon=docker&label=image%20size)](https://hub.docker.com/r/gounux/gischat/)

![Github stars](https://badgen.net/github/stars/geotribu/gischat?icon=github&label=stars)
![Github forks](https://badgen.net/github/forks/geotribu/gischat?icon=github&label=forks)
![Github issues](https://img.shields.io/github/issues/geotribu/gischat)
![Github last-commit](https://img.shields.io/github/last-commit/geotribu/gischat)

---

Gischat API backend for chatting with your tribe in GIS tools like QGIS (using [QTribu](https://github.com/geotribu/qtribu) plugin available [from official plugin repository](https://plugins.qgis.org/plugins/qtribu/)), QField and other to come

**No database : messages are not stored. Just stateless websockets.**

## Known instances

Following instances are up and running :

| URL | Description | Location |
|-----|-------------|----------|
|https://gischat.geotribu.net|"official" international instance| Germany|
|https://gischat.geotribu.fr|"official" french-speaking instance| Germany|

## Developer information

- Rooms can be fetched using [the `/rooms` endpoint](https://gischat.geotribu.net/docs#/default/get_rooms_rooms_get)
- Rules can be fetched using [the `/rules` endpoint](https://gischat.geotribu.net/docs#/default/get_rules_rules_get)
- Number of connected users can be fetched using [the `/status` endpoint](https://gischat.geotribu.net/docs#/default/get_status_status_get)
- New users must connect a websocket to the `/room/{room_name}/ws` endpoint
- Messages passing through the websocket are simple JSON dicts like this: `{"message": "hello", "author": "Hans Hibbel"}`
- :warning: Messages having the `"internal"` author are internal messages and should not be printed, they contain technical information: `{"author": "internal", "nb_users": 36}`
- `"author"` value must be alphanumeric (or `_` or `-`) and have min / max length set by `MIN_AUTHOR_LENGTH` / `MAX_AUTHOR_LENGTH` environment variables
- `"message"` value must have max length set by `MAX_MESSAGE_LENGTH` environment variable

## Deploy a self-hosted instance

### Setup Gischat backend

- Install `docker` using [the official documentation](https://docs.docker.com/engine/install/)

- Create a `docker-compose.yaml` file on your server :

```sh
services:
  api:
    image: gounux/gischat:latest
    container_name: gischat-app
    environment:
      - ROOMS=QGIS,Field and mobile,GIS tribe, Living room,Kitchen,Garden
      - RULES=Be kind and nice to this wonderful world
      - MAIN_LANGUAGE=en
      - ENVIRONMENT=production
      - MIN_AUTHOR_LENGTH=3
      - MAX_AUTHOR_LENGTH=32
      - MAX_MESSAGE_LENGTH=255
    ports:
      - 8000:8000
    restart: unless-stopped
```

`ROOMS` environment variable is a comma-separated list of strings which represent the available chat rooms  
`RULES` environment variable describes the instance's rules


- Launch the app using `compose` :

```sh
docker compose up -d
```

- Have a look at the logs :

```sh
docker compose logs -f
```

### Run behind a nginx proxy using HTTPS

- Install nginx and certbot

```sh
apt install nginx certbot
```

- Get a Let's Encrypt SSL certificate for your domain :

```sh
# stop nginx service
systemctl stop nginx
# get the certificate
certbot certonly --standalone -d DOMAIN
# restart nginx service
systemctl start nginx
```

The Let's Encrypt SSL certificate should be saved to `/etc/letsencrypt/live/DOMAIN`

- Create a nginx config file :

```sh
touch /etc/nginx/sites-available/gischat.conf
```

- Edit the file and add the following content (using your domain):

```sh
upstream gischat_upstream {
  server 127.0.0.1:8000;
}

server {
  listen 80;
  server_name <DOMAIN>;
  return 301 https://$host$request_uri;
}

server {

  listen 443 ssl;
  server_name <DOMAIN>;

  ssl_certificate /etc/letsencrypt/live/<DOMAIN>/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/<DOMAIN>/privkey.pem;

  location / {
    proxy_pass http://gischat_upstream;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400;
  }
}
```

- Create a symlink to enable the nginx config file :

```sh
ln -s /etc/nginx/sites-available/gischat.conf /etc/nginx/sites-enabled/gischat.conf
```

- Check that the nginx config file is okey :

```sh
nginx -t
```

You should see something like this :

```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

- Reload nginx configuration

```sh
systemctl reload nginx
```

That's it, you should be able to chat now with your fellow GIS mates !

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

- Create local environment file and edit it:

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
docker run geotribu/gischat:latest --env ROOMS=QGIS,QField,Geotribu --env RULES="Those are the rules: ..."
```
