# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

# This might work, but probably only with syncronous backends
# as it looks like sqlmodel runs asyncio database operations
# in a greenlet thread

from __future__ import annotations

from typing import AsyncIterator

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import Field, SQLModel, create_engine, func, select

from . import settings


class Scope(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)


class ScopeList(SQLModel, table=True):
    scope_id: int | None = Field(default=None, foreign_key="scope.id", primary_key=True)
    object_id: int | None = Field(
        default=None, foreign_key="object.id", primary_key=True
    )


class Shard(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(unique=True)


class Object(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(unique=True)
    shard_id: int | None = Field(default=None, foreign_key="shard.id")
    offset: int
    end: int


engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)


async def create_scope_db():
    async with engine.begin() as con:
        await con.run_sync(SQLModel.metadata.create_all)


async def count_items_in_scope(scope: str) -> int:
    async with AsyncSession(engine) as session:
        stmt = (
            select(func.count())
            .select_from(ScopeList)
            .join(Scope)
            .where(Scope.name == scope)
        )
        return await session.exec(stmt).one()


async def get_items_in_scope(
    scope: str, shard: int
) -> AsyncIterator[tuple[str, int, int]]:
    limit = settings.BATCH_SIZE
    offset = shard * settings.BATCH_SIZE

    async with AsyncSession(engine) as session:
        stmt = (
            select(Shard.url, Object.offset, Object.end)
            .join(Shard)
            .join(ScopeList)
            .join(Scope)
            .where(Scope.name == scope)
            .limit(limit)
            .offset(offset)
        )
        result = await session.exec(stmt)
        async for url, offset, end in result:
            yield url, offset, end
