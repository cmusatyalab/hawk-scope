# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

from sqlalchemy import ForeignKey, func, select
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from . import settings


class SQLTable(AsyncAttrs, DeclarativeBase):
    pass


class Scope(SQLTable):
    __tablename__ = "scope"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class ScopeList(SQLTable):
    __tablename__ = "scopelist"

    scope_id: Mapped[int] = mapped_column(ForeignKey("scope.id"), primary_key=True)
    object_id: Mapped[int] = mapped_column(ForeignKey("object.id"), primary_key=True)


class Shard(SQLTable):
    __tablename__ = "shard"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(unique=True)


class Object(SQLTable):
    __tablename__ = "object"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(unique=True)
    shard_id: Mapped[int] = mapped_column(ForeignKey("shard.id"))
    offset: Mapped[int]
    end: Mapped[int]


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)


async def create_scope_db() -> None:
    async with engine.begin() as con:
        await con.run_sync(SQLTable.metadata.create_all)


async def build_shard_index(shard: str, items: Iterable[tuple[str, int, int]]) -> None:
    async with AsyncSession(engine) as session:
        shard = Shard(url=shard)
        await session.add(shard)
        await session.commit()

        for key, off, end in items:
            obj = Object(key=key, shard_id=shard.id, offset=off, end=end)
            await session.add(obj)
        await session.commit()


async def count_items_in_scope(scope: str) -> int:
    async with AsyncSession(engine) as session:
        stmt = (
            select(func.count("*"))
            .select_from(ScopeList)
            .join(Scope)
            .where(Scope.name == scope)
        )
        result = await session.execute(stmt)
        return result.scalars().one()


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
        result = await session.execute(stmt)
        for url, offset, end in result:
            yield url, offset, end
