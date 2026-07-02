# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

from sqlalchemy import ForeignKey, delete, func, select
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from . import settings
from .util import batched


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
        session.add(shard)
        await session.flush()

        # There is no real reason to batch here, I think
        # the typical shard contains only about 10k-25k object
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
        result = await session.execute(stmt)
        for name, n in result:
            yield name, n


async def import_scope(scope: str, items: Iterable[str]) -> None:
    async with AsyncSession(engine) as session:
        scope_obj = Scope(name=scope)
        session.add(scope_obj)

        # Here we have to batch because the in_ operator only accepts up to N
        # variables, which seems to be between 900 and 1000 for sqlite3 and
        # a scope can easily refer to 200k objects or more.
        # we might need to use lower level insert operations if we want to
        # reduce memory overhead on significantly larger scope lists.
        for batch in batched(items, 900):
            stmt = select(Object).where(Object.key.in_(batch))
            results = await session.execute(stmt)
            session.add_all(
                [
                    ScopeList(scope_id=scope_obj.id, object_id=obj.id)
                    for (obj,) in results
                ]
            )
            session.flush()
        await session.commit()


async def export_scope(scope: str) -> AsyncIterator[str]:
    async with AsyncSession(engine) as session:
        stmt = select(Object.key).join(ScopeList).join(Scope).where(Scope.name == scope)
        result = await session.execute(stmt)
        for (name,) in result:
            yield name


async def delete_scope(scope: str) -> None:
    async with AsyncSession(engine) as session:
        stmt = select(Scope).where(Scope.name == scope)
        result = await session.execute(stmt)
        scope_obj = result.one()[0]

        stmt = delete(ScopeList).where(ScopeList.scope_id == scope_obj.id)
        await session.execute(stmt)
        await session.delete(scope_obj)
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
            .order_by(Object.shard_id, Object.offset)
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        for url, offset, end in result:
            yield url, offset, end
