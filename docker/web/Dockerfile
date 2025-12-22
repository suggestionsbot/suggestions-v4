FROM ghcr.io/astral-sh/uv:python3.13-alpine

RUN apk update
RUN apk add bash gcc

WORKDIR /code

## Program install steps
COPY ./pyproject.toml /code/pyproject.toml
COPY ./uv.lock /code/uv.lock

RUN uv sync --compile-bytecode

COPY . /code

RUN chmod +x /code/docker/web/entrypoint.sh
ENTRYPOINT ["/code/docker/web/entrypoint.sh"]
