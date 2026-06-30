# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel, col, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from . import settings
from .compat import batched


class Scope(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)


class ScopeList(SQLModel, table=True):
    scope_id: int = Field(primary_key=True, foreign_key="scope.id", ondelete="CASCADE")
    object_id: int = Field(
        primary_key=True, foreign_key="object.id", ondelete="RESTRICT"
    )


class Shard(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(unique=True)


class Object(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(unique=True)
    shard_id: int = Field(foreign_key="shard.id", ondelete="CASCADE")
    offset: int
    end: int


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)


async def create_scope_db():
    async with engine.begin() as con:
        await con.run_sync(SQLModel.metadata.create_all)


async def build_shard_index(shard: str, items: Iterable[tuple[str, int, int]]) -> None:
    async with AsyncSession(engine) as session:
        shard = Shard(url=shard)
        session.add(shard)
        await session.flush()

        session.add_all(
            [
                Object(key=key, shard_id=shard.id, offset=off, end=end)
                for key, off, end in items
            ]
        )
        await session.commit()


async def list_scopes() -> AsyncIterator[tuple[str, int]]:
    async with AsyncSession(engine) as session:
        stmt = (
            select(Scope.name, func.count(ScopeList.object_id))
            .join(ScopeList, isouter=True)
            .group_by(ScopeList.scope_id)
            .order_by(Scope.name)
        )
        result = await session.exec(stmt)
        for name, n in result:
            yield name, n


async def import_scope(scope: str, items: Iterable[str]) -> None:
    async with AsyncSession(engine) as session:
        scope_obj = Scope(name=scope)
        session.add(scope_obj)
        await session.flush()

        for batch in batched(items, 1000):
            stmt = select(Object).where(col(Object.key).in_(batch))
            results = await session.exec(stmt)

            session.add_all(
                [ScopeList(scope_id=scope_obj.id, object_id=obj.id) for obj in results]
            )
            session.flush()
        await session.commit()


async def export_scope(scope: str) -> AsyncIterator[str]:
    async with AsyncSession(engine) as session:
        stmt = select(Object.key).join(ScopeList).join(Scope).where(Scope.name == scope)
        result = await session.exec(stmt)
        for name in result:
            yield name


async def delete_scope(scope: str) -> None:
    async with AsyncSession(engine) as session:
        stmt = select(Scope).where(Scope.name == scope)
        result = await session.exec(stmt)
        scope_obj = result.one()

        stmt = delete(ScopeList).where(ScopeList.scope_id == scope_obj.id)
        await session.exec(stmt)
        await session.delete(scope_obj)
        await session.commit()


async def count_items_in_scope(scope: str) -> int:
    async with AsyncSession(engine) as session:
        stmt = (
            select(func.count())
            .select_from(ScopeList)
            .join(Scope)
            .where(Scope.name == scope)
        )
        result = await session.exec(stmt)
        return result.one()


async def get_items_in_scope(
    scope: str, shard: int
) -> AsyncIterator[tuple[str, int, int]]:
    limit = settings.BATCH_SIZE
    offset = shard * settings.BATCH_SIZE

    async with AsyncSession(engine) as session:
        stmt = (
            select(Shard.url, Object.offset, Object.end)
            .select_from(Object)
            .join(Shard)
            .join(ScopeList)
            .join(Scope)
            .where(Scope.name == scope)
            .order_by(Object.shard_id, Object.offset)
            .limit(limit)
            .offset(offset)
        )
        result = await session.exec(stmt)
        for url, offset, end in result:
            yield url, offset, end
