# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterable, AsyncIterator
from importlib.resources import files
from typing import TYPE_CHECKING

import typer
from rich import print
from starlette.applications import Starlette
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
    requires,
)
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from . import settings
from .db import export_scope, get_items_in_scope, import_scope
from .slicer import generate_shard, generate_wids_descriptor

if TYPE_CHECKING:
    from starlette.requests import Request


class APIKeyAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if "X-API-Key" not in conn.headers:
            return

        api_key = conn.headers["X-API-Key"]
        if api_key != str(settings.API_KEY):
            raise AuthenticationError("Invalid X-API-Key")

        return AuthCredentials(["apikey"]), SimpleUser("API")


async def root(request: Request) -> FileResponse:
    animation = files("hawk_scope").joinpath("webdataset-animation.html")
    return FileResponse(animation, media_type="text/html")


async def get_wids(request: Request) -> JSONResponse:
    scope = request.path_params["scope"]
    base_url = str(request.base_url)
    wids_descriptor = await generate_wids_descriptor(scope, base_url)
    return JSONResponse(wids_descriptor)


async def get_shard(request: Request) -> StreamingResponse:
    scope = request.path_params["scope"]
    shard = request.path_params["shard"]
    items = get_items_in_scope(scope, shard)
    object_stream = generate_shard(items)
    return StreamingResponse(object_stream, media_type="application/x-tar")


async def get_scope(request: Request) -> StreamingResponse:
    scope = request.path_params["scope"]
    items = (f"{key}\n" async for key in export_scope(scope))
    return StreamingResponse(items, media_type="text/plain")


async def chunks_to_lines(stream: AsyncIterable[bytes]) -> AsyncIterator[str]:
    """Helper to convert a stream of binary chunks to lines"""
    body = ""
    async for chunk in stream:
        body += chunk.decode()
        while "\n" in body:
            line, body = body.split("\n", 1)
            line = line.strip()
            if line:
                yield line
        # handle the case when there are no newlines in the input
        if len(body) > 4096:
            msg = "Input line too long"
            raise BufferError(msg)
    line = body.strip()
    if line:
        yield line


@requires("apikey")
async def create_scope(request: Request) -> Response:
    scope = request.path_params["scope"]
    try:
        items = chunks_to_lines(request.stream())
        await import_scope(scope, items)
        return Response(status_code=204)
    except FileExistsError as e:
        # scope already exists
        return Response(e.args[0], status_code=409)
    except KeyError as e:
        # Duplicate or unknown object in scope list
        return Response(e.args[0], status_code=400)
    except (BufferError, UnicodeDecodeError):
        # unable to parse the request.body stream to object ids
        return Response("Unable to process scope list", status_code=400)


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> None:
    if str(settings.API_KEY) == str(settings.SESSION_KEY):
        print(f"[red]NOTE:[/red]\t  Temporary API key is: {settings.API_KEY}")
    yield


app = Starlette(
    debug=settings.DEBUG,
    routes=[
        Route("/", root),
        Route("/{scope}.json", get_wids),
        Route("/{scope}-{shard:int}.tar", get_shard, name="shard"),
        Route("/{scope}.scope", get_scope),
        Route("/{scope}.scope", create_scope, methods=["POST"]),
    ],
    middleware=[
        Middleware(AuthenticationMiddleware, backend=APIKeyAuthBackend()),
    ],
    lifespan=lifespan,
)

cli = typer.Typer()


@cli.command()
def serve(host: str = "0.0.0.0", port: int = 5000) -> None:
    """Run a webserver instance to generate scoped datasets."""
    import uvicorn

    uvicorn.run("hawk_scope.web:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    cli()
