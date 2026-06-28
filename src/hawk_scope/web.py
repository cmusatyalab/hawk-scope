# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

from importlib.resources import files
from typing import TYPE_CHECKING

import typer
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Route

from . import settings
from .slicer import generate_wids_descriptor, get_items_in_scope, generate_shard

if TYPE_CHECKING:
    from starlette.requests import Request


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


async def root(request: Request) -> FileResponse:
    animation = files("hawk_scope").joinpath("webdataset-animation.html")
    return FileResponse(animation, media_type="text/html")


app = Starlette(
    debug=settings.DEBUG,
    routes=[
        Route("/", root),
        Route("/{scope}.json", get_wids),
        Route("/{scope}-{shard:int}.tar", get_shard, name="shard"),
    ],
)

cli = typer.Typer()


@cli.command()
def serve(host: str = "0.0.0.0", port: int = 5000) -> None:
    """Run a webserver instance"""
    import uvicorn

    uvicorn.run("hawk_scope.web:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    cli()
