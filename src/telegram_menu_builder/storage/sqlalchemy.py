"""Async SQL storage backend built on SQLAlchemy 2.0 Core.

This backend persists callback payloads in a relational database using the
SQLAlchemy 2.0 async engine and Core constructs (not the ORM). A single code
path supports PostgreSQL/Supabase, MySQL/MariaDB, and SQLite by branching on the
active dialect only for the UPSERT statement.

Install the optional dependencies with one of::

    pip install "telegram-menu-builder[sql]"        # SQLAlchemy + SQLite
    pip install "telegram-menu-builder[postgres]"   # + asyncpg driver
    pip install "telegram-menu-builder[mysql]"       # + asyncmy driver

Example:
    >>> store = SQLAlchemyStorage(database_url="sqlite+aiosqlite:///:memory:")
    >>> await store.create_schema()
    >>> await store.set("k", {"h": "menu", "p": {}}, ttl=60)
    >>> await store.get("k")
    {'h': 'menu', 'p': {}}
    >>> await store.close()
"""

import datetime
from typing import Any, cast

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Dialect,
    MetaData,
    String,
    Table,
    TypeDecorator,
    case,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.elements import BinaryExpression

from telegram_menu_builder.storage.base import BaseStorage
from telegram_menu_builder.types import StorageError


def _utcnow() -> datetime.datetime:
    """Return the current time as a timezone-aware UTC datetime.

    This indirection exists so tests can monkeypatch the notion of "now" to
    exercise TTL expiry deterministically.

    Returns:
        The current moment as a timezone-aware :class:`datetime.datetime`.
    """
    return datetime.datetime.now(datetime.UTC)


class UtcDateTime(TypeDecorator[datetime.datetime]):
    """A timezone-aware ``DateTime`` that always round-trips in UTC.

    SQLite (and some driver/dialect combinations) drop or misreport timezone
    information. This decorator normalises every value to UTC before binding it
    to a parameter and re-attaches UTC ``tzinfo`` to values read back from the
    database, so the Python side always sees aware UTC datetimes.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime.datetime | None, dialect: Dialect
    ) -> datetime.datetime | None:
        """Coerce a value to UTC before sending it to the database.

        Args:
            value: The datetime to store (naive values are assumed to be UTC).
            dialect: The active SQLAlchemy dialect (unused).

        Returns:
            A timezone-aware UTC datetime, or ``None``.
        """
        del dialect  # Part of the TypeDecorator override contract; unused here.
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.UTC)
        return value.astimezone(datetime.UTC)

    def process_result_value(
        self, value: datetime.datetime | None, dialect: Dialect
    ) -> datetime.datetime | None:
        """Re-attach UTC ``tzinfo`` to a value read from the database.

        Args:
            value: The datetime returned by the driver (possibly naive).
            dialect: The active SQLAlchemy dialect (unused).

        Returns:
            A timezone-aware UTC datetime, or ``None``.
        """
        del dialect  # Part of the TypeDecorator override contract; unused here.
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.UTC)
        return value.astimezone(datetime.UTC)


def _glob_to_like(pattern: str) -> str:
    """Translate a shell-style glob pattern into a SQL ``LIKE`` pattern.

    The literal ``LIKE`` wildcards (``%`` and ``_``) and the backslash escape
    character are first escaped, then the glob wildcards ``*`` and ``?`` are
    mapped to ``%`` and ``_`` respectively.

    Args:
        pattern: A glob pattern using ``*`` and ``?``.

    Returns:
        A ``LIKE`` pattern to be used with ``escape="\\"``.
    """
    out = pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return out.replace("*", "%").replace("?", "_")


class SQLAlchemyStorage(BaseStorage):
    """Async SQL storage backend using SQLAlchemy 2.0 Core.

    Stores callback payloads in a single table with columns ``key`` (bounded
    string primary key), ``value`` (JSON) and ``expires_at`` (nullable, indexed
    timezone-aware datetime). Works across PostgreSQL/Supabase, MySQL/MariaDB
    and SQLite from one code path; only the UPSERT statement is dialect-aware.

    Engine ownership:
        If constructed from a ``database_url`` the backend creates and OWNS the
        engine and disposes it on :meth:`close`. If an existing ``engine`` is
        supplied the backend BORROWS it and never disposes it.

    Example:
        >>> store = SQLAlchemyStorage(database_url="sqlite+aiosqlite:///:memory:")
        >>> await store.create_schema()
        >>> await store.set("k", {"h": "menu", "p": {"x": 1}})
        >>> await store.get("k")
        {'h': 'menu', 'p': {'x': 1}}
        >>> await store.close()

    Note:
        Unlike :class:`~telegram_menu_builder.storage.memory.MemoryStorage`,
        :meth:`get_stats` here is asynchronous because it queries the database.
    """

    def __init__(
        self,
        database_url: str | None = None,
        *,
        engine: AsyncEngine | None = None,
        table_name: str = "menu_callbacks",
        schema: str | None = None,
    ) -> None:
        """Initialize the SQL storage backend.

        Exactly one of ``database_url`` or ``engine`` must be supplied.

        Args:
            database_url: An async SQLAlchemy URL (e.g.
                ``"postgresql+asyncpg://..."``, ``"mysql+asyncmy://..."`` or
                ``"sqlite+aiosqlite:///:memory:"``). When given, an engine is
                created and owned by this instance.
            engine: An existing :class:`~sqlalchemy.ext.asyncio.AsyncEngine` to
                borrow. When given, it is NOT disposed on :meth:`close`.
            table_name: Name of the table holding callback payloads.
            schema: Optional database schema/namespace for the table.

        Raises:
            ValueError: If neither or both of ``database_url`` and ``engine``
                are provided.
        """
        super().__init__()

        if (database_url is None) == (engine is None):
            msg = (
                "Exactly one of 'database_url' or 'engine' must be provided (got both or neither)."
            )
            raise ValueError(msg)

        self._owns_engine: bool
        self._engine: AsyncEngine
        if database_url is not None:
            self._engine = self._create_engine(database_url)
            self._owns_engine = True
        else:
            # engine is not None here (guaranteed by the XOR check above).
            assert engine is not None
            self._engine = engine
            self._owns_engine = False

        self._metadata = MetaData()
        self._table = Table(
            table_name,
            self._metadata,
            Column("key", String(255), primary_key=True),
            Column("value", JSON, nullable=False),
            Column("expires_at", UtcDateTime, nullable=True, index=True),
            schema=schema,
        )

    @staticmethod
    def _create_engine(database_url: str) -> AsyncEngine:
        """Create an owned async engine from a URL.

        In-memory SQLite URLs require a :class:`~sqlalchemy.pool.StaticPool` and
        ``check_same_thread=False`` so the single underlying connection persists
        across operations; otherwise the async pool would hand out fresh
        connections and lose the data.

        Args:
            database_url: The async database URL.

        Returns:
            A newly created :class:`~sqlalchemy.ext.asyncio.AsyncEngine`.
        """
        if ":memory:" in database_url:
            return create_async_engine(
                database_url,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
        return create_async_engine(database_url)

    def _not_expired(self, now: datetime.datetime) -> ColumnElement[bool]:
        """Build the "not expired" predicate for queries.

        Args:
            now: The reference moment (timezone-aware UTC).

        Returns:
            A boolean column expression that is true for rows without an expiry
            or whose expiry is strictly in the future.
        """
        expires_at = self._table.c.expires_at
        return (expires_at.is_(None)) | (expires_at > now)

    async def create_schema(self) -> None:
        """Create the backing table and indexes if they do not exist.

        This is idempotent: it uses ``checkfirst=True`` so it can be called
        repeatedly without error.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the DDL operation fails.
        """
        self._ensure_open()
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(self._metadata.create_all, checkfirst=True)
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to create schema: {exc}") from exc

    async def drop_schema(self) -> None:
        """Drop the backing table if it exists.

        This is idempotent thanks to ``checkfirst=True``.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the DDL operation fails.
        """
        self._ensure_open()
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(self._metadata.drop_all, checkfirst=True)
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to drop schema: {exc}") from exc

    async def set(self, key: str, data: dict[str, Any], ttl: int | None = None) -> None:
        """Store (UPSERT) data under ``key`` with an optional TTL.

        Re-setting the same key overwrites the existing value and refreshes (or
        clears) its expiry, matching the encoder's deterministic-key dedup.

        Args:
            key: Unique identifier for the data.
            data: JSON-serializable dictionary to store.
            ttl: Time-to-live in seconds (``None`` = no expiration).

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the write fails.
        """
        self._ensure_open()

        expires_at = _utcnow() + datetime.timedelta(seconds=ttl) if ttl is not None else None
        values = {"key": key, "value": data, "expires_at": expires_at}

        try:
            stmt = self._build_upsert(values)
            if stmt is None:
                # Dialect without native UPSERT: fall back to DELETE-then-INSERT.
                await self._fallback_set(values)
            else:
                async with self._engine.begin() as conn:
                    await conn.execute(stmt)
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to set key {key!r}: {exc}") from exc

    def _build_upsert(self, values: dict[str, Any]) -> Any:
        """Build a dialect-specific UPSERT statement.

        Branches on ``self._engine.dialect.name``:

        * ``postgresql`` / ``sqlite``: ``INSERT ... ON CONFLICT DO UPDATE``.
        * ``mysql`` / ``mariadb``: ``INSERT ... ON DUPLICATE KEY UPDATE``.
        * otherwise (fallback): a delete-by-key statement; :meth:`set` runs the
          fallback as DELETE-then-INSERT inside one transaction. Because the
          fallback needs two statements, ``set`` handles it specially when this
          method returns ``None``.

        Args:
            values: The row values to insert (``key``, ``value``, ``expires_at``).

        Returns:
            An executable insert statement for known dialects.
        """
        dialect = self._engine.dialect.name

        if dialect in ("postgresql", "sqlite"):
            pg_or_sqlite = pg_insert if dialect == "postgresql" else sqlite_insert
            stmt = pg_or_sqlite(self._table).values(**values)
            return stmt.on_conflict_do_update(
                index_elements=[self._table.c.key],
                set_={
                    "value": stmt.excluded.value,
                    "expires_at": stmt.excluded.expires_at,
                },
            )

        if dialect in ("mysql", "mariadb"):
            my_stmt = mysql_insert(self._table).values(**values)
            return my_stmt.on_duplicate_key_update(
                value=my_stmt.inserted.value,
                expires_at=my_stmt.inserted.expires_at,
            )

        # Fallback for any other dialect: signal DELETE-then-INSERT to set().
        return None

    async def _fallback_set(self, values: dict[str, Any]) -> None:
        """Emulate UPSERT on dialects without native conflict handling.

        Performs ``DELETE WHERE key`` then ``INSERT`` inside a single
        transaction so the operation is atomic.

        Args:
            values: The row values (``key``, ``value``, ``expires_at``).
        """
        async with self._engine.begin() as conn:
            await conn.execute(delete(self._table).where(self._table.c.key == values["key"]))
            await conn.execute(self._table.insert().values(**values))

    async def add(self, key: str, data: dict[str, Any], ttl: int | None = None) -> bool:
        """Atomically store ``data`` under ``key`` only if it is absent.

        The whole operation runs inside a SINGLE transaction
        (``async with self._engine.begin()``) so it is atomic against concurrent
        callers and the engine's connection pool. Within that transaction it:

        1. DELETEs any row for ``key`` whose TTL has already elapsed
           (``expires_at IS NOT NULL AND expires_at <= now``), freeing an expired
           claim so it can be reclaimed; and then
        2. runs a dialect INSERT that no-ops on a primary-key conflict, mirroring
           the dialect branches of :meth:`_build_upsert`: PostgreSQL/SQLite use
           ``INSERT ... ON CONFLICT DO NOTHING``; MySQL/MariaDB use
           ``INSERT IGNORE``; any other dialect falls back to a plain INSERT and
           treats an :class:`~sqlalchemy.exc.IntegrityError` as a lost race.

        The boolean result is derived from the INSERT's affected-row count: a row
        was inserted (won the claim) iff ``rowcount > 0``.

        Args:
            key: Unique identifier for the data.
            data: JSON-serializable dictionary to store.
            ttl: Time-to-live in seconds (``None`` = no expiration).

        Returns:
            ``True`` if this call stored the value, ``False`` if a live
            (non-expired) row already existed for the key.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the write fails.
        """
        self._ensure_open()

        now = _utcnow()
        expires_at = now + datetime.timedelta(seconds=ttl) if ttl is not None else None
        values = {"key": key, "value": data, "expires_at": expires_at}

        try:
            async with self._engine.begin() as conn:
                # Free an expired claim first so it can be reclaimed in this txn.
                expires_col = self._table.c.expires_at
                await conn.execute(
                    delete(self._table).where(
                        (self._table.c.key == key)
                        & (expires_col.is_not(None))
                        & (expires_col <= now)
                    )
                )

                stmt = self._build_insert_ignore(values)
                if stmt is None:
                    # Dialect without a native no-op insert: try a plain INSERT and
                    # treat a primary-key collision as a lost race.
                    try:
                        result = await conn.execute(self._table.insert().values(**values))
                    except IntegrityError:
                        return False
                    return result.rowcount > 0

                result = await conn.execute(stmt)
                return result.rowcount > 0
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to add key {key!r}: {exc}") from exc

    def _build_insert_ignore(self, values: dict[str, Any]) -> Any:
        """Build a dialect-specific INSERT that no-ops on a primary-key conflict.

        Branches on ``self._engine.dialect.name``, mirroring :meth:`_build_upsert`:

        * ``postgresql`` / ``sqlite``: ``INSERT ... ON CONFLICT DO NOTHING``.
        * ``mysql`` / ``mariadb``: ``INSERT IGNORE``.
        * otherwise (fallback): ``None``, signalling :meth:`add` to attempt a
          plain INSERT and catch :class:`~sqlalchemy.exc.IntegrityError`.

        Args:
            values: The row values to insert (``key``, ``value``, ``expires_at``).

        Returns:
            An executable conflict-tolerant insert statement for known dialects,
            or ``None`` to request the generic INSERT/``IntegrityError`` fallback.
        """
        dialect = self._engine.dialect.name

        if dialect in ("postgresql", "sqlite"):
            pg_or_sqlite = pg_insert if dialect == "postgresql" else sqlite_insert
            stmt = pg_or_sqlite(self._table).values(**values)
            return stmt.on_conflict_do_nothing(index_elements=[self._table.c.key])

        if dialect in ("mysql", "mariadb"):
            return mysql_insert(self._table).values(**values).prefix_with("IGNORE")

        # Fallback for any other dialect: signal plain INSERT to add().
        return None

    async def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve the (non-expired) value stored under ``key``.

        Expiry is filtered lazily at query time; an expired row is treated as
        missing and ``None`` is returned (the row is not eagerly deleted here).

        Args:
            key: Unique identifier for the data.

        Returns:
            The stored dictionary, or ``None`` if missing or expired.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the read fails.
        """
        self._ensure_open()

        now = _utcnow()
        stmt = select(self._table.c.value).where(
            (self._table.c.key == key) & self._not_expired(now)
        )
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(stmt)
                raw = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to get key {key!r}: {exc}") from exc

        if raw is None:
            return None
        return cast("dict[str, Any]", raw)

    async def delete(self, key: str) -> bool:
        """Delete the row stored under ``key``.

        Args:
            key: Unique identifier for the data.

        Returns:
            ``True`` if a row was deleted, ``False`` if the key did not exist.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the delete fails.
        """
        self._ensure_open()

        stmt = delete(self._table).where(self._table.c.key == key)
        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(stmt)
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to delete key {key!r}: {exc}") from exc

        return result.rowcount > 0

    async def exists(self, key: str) -> bool:
        """Check whether a non-expired row exists under ``key``.

        Args:
            key: Unique identifier to check.

        Returns:
            ``True`` if the key exists and has not expired.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the read fails.
        """
        self._ensure_open()

        now = _utcnow()
        stmt = select(self._table.c.key).where((self._table.c.key == key) & self._not_expired(now))
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(stmt)
                row = result.first()
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to check existence of key {key!r}: {exc}") from exc

        return row is not None

    async def clear(self) -> None:
        """Delete every row in the backing table.

        Warning:
            This removes ALL stored callbacks. Use with care in production.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the delete fails.
        """
        self._ensure_open()

        try:
            async with self._engine.begin() as conn:
                await conn.execute(delete(self._table))
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to clear storage: {exc}") from exc

    async def keys(self, pattern: str | None = None) -> list[str]:
        """Return all non-expired keys, optionally filtered by a glob pattern.

        The glob ``pattern`` is translated to a SQL ``LIKE`` clause and pushed
        down to the database.

        Note:
            This diverges from :class:`MemoryStorage`'s ``fnmatch`` semantics:
            SQL ``LIKE`` supports only ``*``/``?`` (mapped to ``%``/``_``) and
            has no ``[seq]`` character-class wildcards.

        Args:
            pattern: Optional glob pattern using ``*`` and ``?``.

        Returns:
            A list of matching, non-expired keys.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the read fails.
        """
        self._ensure_open()

        now = _utcnow()
        condition: ColumnElement[bool] = self._not_expired(now)
        if pattern is not None:
            like_clause: BinaryExpression[bool] = self._table.c.key.like(
                _glob_to_like(pattern), escape="\\"
            )
            condition = condition & like_clause

        stmt = select(self._table.c.key).where(condition)
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(stmt)
                rows = result.scalars().all()
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to list keys: {exc}") from exc

        return list(rows)

    async def cleanup_expired(self) -> int:
        """Delete all rows whose TTL has elapsed.

        Returns:
            The number of expired rows removed.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the delete fails.
        """
        self._ensure_open()

        now = _utcnow()
        expires_at = self._table.c.expires_at
        stmt = delete(self._table).where((expires_at.is_not(None)) & (expires_at <= now))
        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(stmt)
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to clean up expired keys: {exc}") from exc

        return result.rowcount

    async def get_stats(self) -> dict[str, int]:
        """Return counts describing the stored keys.

        Note:
            This method is asynchronous (it queries the database), unlike the
            synchronous ``get_stats`` on
            :class:`~telegram_menu_builder.storage.memory.MemoryStorage`.

        Returns:
            A mapping with the keys ``total_keys``, ``keys_with_ttl``,
            ``expired_keys`` and ``active_keys``.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the read fails.
        """
        self._ensure_open()

        now = _utcnow()
        expires_at = self._table.c.expires_at
        is_expired = (expires_at.is_not(None)) & (expires_at <= now)
        # One aggregate query: total rows, rows with a TTL, and expired rows.
        # The expired count uses SUM(CASE ...) rather than COUNT(...) FILTER so it
        # stays portable across MySQL/MariaDB, which do not support the FILTER clause.
        stmt = select(
            func.count().label("total"),
            func.count(expires_at).label("with_ttl"),
            func.coalesce(func.sum(case((is_expired, 1), else_=0)), 0).label("expired"),
        )
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(stmt)
                row = result.one()
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to compute stats: {exc}") from exc

        total = int(row.total)
        with_ttl = int(row.with_ttl)
        expired_count = int(row.expired)
        return {
            "total_keys": total,
            "keys_with_ttl": with_ttl,
            "expired_keys": expired_count,
            "active_keys": total - expired_count,
        }

    async def close(self) -> None:
        """Close the storage, disposing the engine only if it is owned.

        A borrowed engine (supplied via ``engine=``) is left intact so the
        caller can keep using it.
        """
        if self._closed:
            return
        if self._owns_engine:
            await self._engine.dispose()
        await super().close()
