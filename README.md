# GISChat - Backend API

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![flake8](https://img.shields.io/badge/linter-flake8-green)](https://flake8.pycqa.org/)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/geotribu/gischat/main.svg)](https://results.pre-commit.ci/latest/github/geotribu/gischat/main)

[![🎳 Tester](https://github.com/geotribu/gischat/actions/workflows/tests.yml/badge.svg)](https://github.com/geotribu/gischat/actions/workflows/tests.yml)
[![🐍 Linter](https://github.com/geotribu/gischat/actions/workflows/lint.yml/badge.svg)](https://github.com/geotribu/gischat/actions/workflows/lint.yml)
[![⚒️ Deploy docker image](https://github.com/geotribu/gischat/actions/workflows/docker.yml/badge.svg)](https://github.com/geotribu/gischat/actions/workflows/docker.yml)
[![codecov](https://codecov.io/github/geotribu/gischat/graph/badge.svg?token=EW5SU9VKRD)](https://codecov.io/github/geotribu/gischat)

---

Gischat API backend for chatting with your tribe in GIS tools.

**No database : messages are not stored. Just stateless websockets.**

## Known clients

Here are the known clients implementing gischat / QChat, at the moment:

- [QChat](https://github.com/geotribu/qchat) QGIS plugin, available [from the official QGIS plugin repository](https://plugins.qgis.org/plugins/qchat/).
- [QField plugin](https://github.com/geotribu/qchat-qfield-plugin).

And other to come!

## Known instances

Following instances are up and running :

| URL | Description | Location |
| :-: | :---------- | :------- |
| <https://qchat.geotribu.net> | Geotribu's official instance | Germany |

## Developer information

- Channel can be fetched using [the `/channels` endpoint](https://qchat.geotribu.net/docs#/default/get_channels_channels_get)
- Rules can be fetched using [the `/rules` endpoint](https://qchat.geotribu.net/docs#/default/get_rules_rules_get)
- Number of connected users can be fetched using [the `/status` endpoint](https://qchat.geotribu.net/docs#/default/get_status_status_get)
- List of connected and registered users can be fetched using [the `/channel/{channel}/users` endpoint](https://qchat.geotribu.net/docs#/default/get_connected_users_channel__channel__users_get)
- New users must connect a websocket to the `/channel/{channel}/ws` endpoint
- After connecting to the websocket, it is possible to register the user in the channel by sending a `newcomer` message (see below)
- Messages passing through the websocket are strings with a JSON structure, they have a `type` key which represent which kind of message it is

### JSON message types

Those are the messages that might transit through the websocket.

Each of them has a `"type"` key based on which it is possible to parse them :

1. `"text"`: basic text message send by someone in the channel, e.g.:

   ```json
   {
     "type": "text",
     "author": "jane_doe",
     "avatar": "mGeoPackage.svg",
     "text": "Hi @all how are you doing ?"
   }
   ```

   > `"author"` value must be alphanumeric (or `_` or `-`) and have min / max length set by `MIN_AUTHOR_LENGTH` / `MAX_AUTHOR_LENGTH` environment variables  
   > `avatar` value is optional and usually points to [a QGIS resource icon](https://github.com/qgis/QGIS/blob/master/images/images.qrc) (see the ones [available in the QChat/QTribu plugin](https://github.com/geotribu/qtribu/blob/e07012628a6c03f2c4ee664025ece0bf7672d245/qtribu/constants.py#L200))  
   > `"text"` value must have max length set by `MAX_MESSAGE_LENGTH` environment variable

1. `"image"`: image message send by someone in the channel, e.g.:

   ```json
   {
     "type": "image",
     "author": "jane_doe",
     "avatar": "mIconPostgis.svg",
     "image_data": "utf-8 string of the image encoded in base64"
   }
   ```

   > The image will be resized by the backend before broadcast, using the `MAX_IMAGE_SIZE` environment variable value

1. `"nb_users"`: notifies about the number of users connected to the channel, e.g.:

   ```json
   {
     "type": "nb_users",
     "nb_users": 36
   }
   ```

1. `"newcomer"`: someone has just registered in the channel, e.g.:

   ```json
   {
     "type": "newcomer",
     "newcomer": "jane_doe"
   }
   ```

   > After having connected to the websocket, it is possible to register a user by sending a `newcomer` message

1. `"exiter"`: someone registered has left the channel, e.g.:

   ```json
   {
     "type": "exiter",
     "exiter": "jane_doe"
   }
   ```

1. `"like"`: someone has liked a message, e.g.:

   ```json
   {
     "type": "like",
     "liker_author": "john_doe",
     "liked_author": "jane_doe",
     "message": "Hi @john_doe how are you doing ?"
   }
   ```

   means that `john_doe` liked `jane_doe`'s message (`"Hi @john_doe how are you doing ?"`)

   > The messages of the `like` type are sent only to the liked author, if this user is registered. If this user is not registered, it won't be notified

1. `"geojson"`: someone shared a geojson layer, e.g.:

   ```json
   {
      "type": "geojson",
      "author": "jane_doe",
      "avatar": "mIconPostgis.svg",
      "layer_name": "my_geojson_layer",
      "crs_wkt": 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]',
      "crs_authid": "EPSG:4326",
      "geojson": {
         "type": "FeatureCollection",
         "features": [
            {
               "type": "Feature",
               "properties": {
                  "attribute_1": "something"
               },
               "geometry": {
                  "type": "Point",
                  "coordinates": [
                     1,
                     2
                  ]
               }
            },
            ...
         ]
      }
   }
   ```

   > The coordinates of the `geojson` features must be expressed using the provided `crs_wkt` and `crs_authid`

1. `"crs"`: someone shared a [CRS](https://en.wikipedia.org/wiki/Spatial_reference_system), e.g.:

   ```json
   {
      "type": "geojson",
      "author": "jane_doe",
      "avatar": "mIconPostgis.svg",
      "crs_wkt": 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]',
      "crs_authid": "EPSG:4326",
   }

   ```

1. `"bbox"`: someone shared a bbox, e.g.:

   ```json
   {
      "type": "bbox",
      "author": "jane_doe",
      "avatar": "mIconPostgis.svg",
      "crs_wkt": 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]',
      "crs_authid": "EPSG:4326",
      "xmin": -1.1,
      "xmax": 1.1,
      "ymin": -1.1,
      "ymax": 1.1
   }
   ```

1. `"position"`: someone shared a position, e.g.:

   ```json
   {
      "type": "bbox",
      "author": "jane_doe",
      "avatar": "mIconPostgis.svg",
      "crs_wkt": 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]',
      "crs_authid": "EPSG:4326",
      "x": 1.234,
      "y": 5.678
   }
   ```

1. `"uncompliant"`: someone sent an uncompliant message and the server answers with such a message, e.g.:

   ```json
   {
      "type": "uncompliant",
      "reason": "Too many geojson features : 600 vs max 500 allowed"
   }
   ```

   > This example is the server response if sending a `ŋeojson` message with too many features

## Deploy a self-hosted instance

### Setup a gischat backend

> [!NOTE]
> `NB_UVICORN_WORKERS` refers to the number of async workers. A usual convenient value would be : (nb_cpu * 2) + 1.
> `CHANNELS` environment variable is a comma-separated list of strings which represent the available chat channels.  
> `RULES` environment variable describes the instance's rules. Useful information that users should know, even when skimming content.  
> `MAX_IMAGE_SIZE` environment variable describes the max size of image in pixels. The server will resize images based on this value.  
> `MAX_GEOJSON_FEATURES` environment variable describes the max number of features allowed in a `geojson` message. If there is more feature, the message will not be considered and the server will respond with a `uncompliant` message.  

1. Install `docker` using [the official documentation](https://docs.docker.com/engine/install/)
1. Create a `docker-compose.yaml` file on your server:

    ```sh
    services:

      api:
        image: gounux/gischat:latest
        container_name: gischat-app
        environment:
          - NB_UVICORN_WORKERS=5
          - CHANNELS=QGIS,Field and mobile,GIS tribe,Kitchen,Garden
          - RULES=Be kind and nice to this wonderful world
          - MAIN_LANG=en
          - INSTANCE_ID=abcdefghijklmnopqrstuvwxyz
          - ENVIRONMENT=production
          - MIN_AUTHOR_LENGTH=3
          - MAX_AUTHOR_LENGTH=32
          - MAX_MESSAGE_LENGTH=255
          - MAX_IMAGE_SIZE=800
          - MAX_GEOJSON_FEATURES=500
          - MAX_STORED_MESSAGES=5
          - REDIS_HOST=redis
        ports:
          - 8000:8000
        restart: unless-stopped

     redis:
       image: redis:latest
       container_name: gischat-redis
       restart: unless-stopped
       volumes:
         - redis-data:/data

   volumes:
     redis-data:
    ```

1. Launch the app using `compose`:

    ```sh
    docker compose up -d
    ```

1. Have a look at the logs:

    ```sh
    docker compose logs -f
    ```

### Run behind a nginx proxy using HTTPS

1. Install nginx and certbot:

    ```sh
    apt install nginx certbot
    ```

1. Get a Let's Encrypt SSL certificate for your domain:

    ```sh
    # stop nginx service
    systemctl stop nginx
    # get the certificate
    certbot certonly --standalone -d DOMAIN
    # restart nginx service
    systemctl start nginx
    ```

    The Let's Encrypt SSL certificate should be saved to `/etc/letsencrypt/live/DOMAIN`

1. Create a nginx config file:

    ```sh
    touch /etc/nginx/sites-available/gischat.conf
    ```

1. Edit the file and add the following content (using your domain):

    ```nginx
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

1. Create a symlink to enable the nginx config file :

    ```sh
    ln -s /etc/nginx/sites-available/gischat.conf /etc/nginx/sites-enabled/gischat.conf
    ```

1. Check that the nginx config file is okey :

    ```sh
    nginx -t
    nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
    nginx: configuration file /etc/nginx/nginx.conf test is successful
    ```

1. Reload nginx configuration

    ```sh
    systemctl reload nginx
    ```

That's it, you should be able to chat now with your fellow GIS mates !

## Development

1. Install [poetry](https://python-poetry.org/):

  ```sh
  python -m pip install poetry
  ```

1. Install [`redis`](https://redis.io/) on your local machine:

  ```sh
  sudo apt install redis-server
  ```

1. Install project's dependencies using poetry:

  ```sh
  poetry install
  ```

1. Install pre-commit tools:

  ```sh
  poetry run pre-commit install
  ```

1. Create local environment file and edit it:

  ```sh
  cp .env.example .env
  ```

1. Launch API:

  ```sh
  poetry run uvicorn gischat.app:app --reload --env-file .env --log-config=log_config.yaml
  ```

## Build

1. Build docker image:

  ```sh
  docker build . --tag geotribu/gischat:latest
  ```

1. Run docker image:

  ```sh
  docker run --env CHANNELS=QGIS,QField,Geotribu --env RULES="Those are the rules: ..." geotribu/gischat:latest
  ```

## Testing

1. Install dev dependencies:

   ```sh
   poetry install --with=dev
   ```

1. Run unit tests:

   ```sh
   poetry run pytest tests
   ```
