"""Async Redis/Valkey storage backend built on redis-py's async client.

A single :class:`RedisStorage` targets BOTH Redis and Valkey. Valkey speaks the
same RESP2/RESP3 wire protocol as Redis, so redis-py's async ``Redis`` client
connects to a Valkey server unchanged -- you simply point a ``redis://`` URL at
the Valkey host. There is intentionally no ``valkey-py`` dependency and no
separate ``ValkeyStorage`` class; a duck-compatible ``valkey.asyncio`` client may
still be supplied via ``client=`` if you prefer.

Install the optional dependency with::

    pip install "telegram-menu-builder[redis]"

Example:
    >>> store = RedisStorage(url="redis://localhost:6379/0")
    >>> await store.set("k", {"h": "menu", "p": {}}, ttl=60)
    >>> await store.get("k")
    {'h': 'menu', 'p': {}}
    >>> await store.close()
"""

import json
from collections.abc import AsyncIterator
from typing import Any, cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from telegram_menu_builder.storage.base import BaseStorage
from telegram_menu_builder.types import StorageError


class RedisStorage(BaseStorage):
    """Async storage backend using redis-py, compatible with Redis and Valkey.

    Callback payloads are stored as JSON strings under a configurable key
    namespace. The backend relies on the server to enforce TTL natively (via the
    ``SET ... EX`` option), so there is no client-side expiry bookkeeping.

    Valkey support:
        Valkey is wire-compatible with Redis, so this same class connects to a
        Valkey server unchanged -- just pass a ``redis://valkey-host`` URL. A
        duck-typed ``valkey.asyncio`` client can also be supplied via ``client=``.

    Client ownership:
        If constructed from a ``url`` the backend creates and OWNS the client and
        closes it on :meth:`close`. If an existing ``client`` is supplied the
        backend BORROWS it and never closes it.

    Namespacing:
        Every key is prefixed with ``namespace`` (default ``"tmb:"``). All
        operations -- including :meth:`clear` and :meth:`keys` -- are scoped to
        that prefix, so multiple stores can safely share one server/database and
        :meth:`clear` never issues ``FLUSHDB``.

    Example:
        >>> store = RedisStorage(url="redis://localhost:6379/0")
        >>> await store.set("k", {"h": "menu", "p": {"x": 1}})
        >>> await store.get("k")
        {'h': 'menu', 'p': {'x': 1}}
        >>> await store.close()

    Note:
        Unlike :class:`~telegram_menu_builder.storage.memory.MemoryStorage`, this
        backend exposes no ``cleanup_expired`` or ``get_stats``: Redis/Valkey
        enforce TTL natively, and server-side introspection is available through
        the ``INFO`` and ``DBSIZE`` commands on :attr:`client`.
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        client: Redis | None = None,
        namespace: str = "tmb:",
    ) -> None:
        """Initialize the Redis/Valkey storage backend.

        Exactly one of ``url`` or ``client`` must be supplied.

        Args:
            url: A redis-py connection URL (e.g. ``"redis://localhost:6379/0"``
                or ``"rediss://..."`` for TLS). A Valkey server is reached via a
                ``redis://valkey-host`` URL. When given, a client is created and
                owned by this instance.
            client: An existing async client to borrow -- a
                :class:`redis.asyncio.Redis` or any duck-compatible async client
                (e.g. ``valkey.asyncio``). When given, it is NOT closed on
                :meth:`close`.
            namespace: Key prefix applied to every stored key (default
                ``"tmb:"``). Scopes :meth:`clear` and :meth:`keys`.

        Raises:
            ValueError: If neither or both of ``url`` and ``client`` are provided.
        """
        super().__init__()

        if (url is None) == (client is None):
            msg = "Exactly one of 'url' or 'client' must be provided (got both or neither)."
            raise ValueError(msg)

        self._client: Redis
        self._owns_client: bool
        if url is not None:
            # redis-py types ``Redis.from_url`` with ``**kwargs: Unknown``, which
            # makes pyright treat even the bare attribute access as partially
            # unknown. Reach it through an ``Any`` reference to the class, then cast
            # the result back to ``Redis``: mypy does not flag this cast as
            # redundant because its source is ``Any``.
            redis_cls: Any = Redis
            self._client = cast("Redis", redis_cls.from_url(url))
            self._owns_client = True
        else:
            # client is not None here (guaranteed by the XOR check above).
            assert client is not None
            self._client = client
            self._owns_client = False

        self._ns = namespace

    @property
    def client(self) -> Redis:
        """Return the underlying redis-py async client.

        Exposed for advanced use and inspection (e.g. ``await store.client.ttl``
        or ``await store.client.info()``).

        Returns:
            The wrapped :class:`redis.asyncio.Redis` client.
        """
        return self._client

    def _k(self, key: str) -> str:
        """Prefix a caller-supplied key with the configured namespace.

        Args:
            key: The unprefixed key as seen by callers.

        Returns:
            The fully namespaced key sent to the server.
        """
        return f"{self._ns}{key}"

    def _to_str(self, value: Any) -> str:
        """Decode a redis-py value to ``str``, handling bytes responses.

        redis-py may return ``bytes`` or ``str`` depending on the client's
        ``decode_responses`` setting; this normalises both to ``str``.

        Args:
            value: A key returned by ``scan_iter`` (``str`` or ``bytes``).

        Returns:
            The value as a ``str``.
        """
        return value.decode() if isinstance(value, (bytes, bytearray)) else value

    async def _scan(self, match: str) -> AsyncIterator[str]:
        """Yield namespaced keys matching ``match`` via ``SCAN``.

        Wraps ``scan_iter`` and normalises each yielded key to ``str``, containing
        redis-py's loosely typed (``Unknown``) async iterator behind a typed
        boundary.

        Args:
            match: A fully namespaced ``SCAN MATCH`` glob pattern.

        Yields:
            Each matching key as a ``str`` (still namespace-prefixed).
        """
        # redis-py types ``scan_iter`` as ``AsyncIterator[Unknown]`` and even its
        # attribute access as partially unknown. Reach it through an ``Any``
        # reference so the yielded values stay contained behind this helper rather
        # than leaking ``Unknown`` into the call sites.
        client: Any = self._client
        iterator: AsyncIterator[Any] = client.scan_iter(match=match)
        async for raw in iterator:
            yield self._to_str(raw)

    async def set(self, key: str, data: dict[str, Any], ttl: int | None = None) -> None:
        """Store ``data`` under ``key`` with an optional TTL.

        The value is serialized to compact JSON. Re-setting the same key
        overwrites the existing value (and resets or clears its expiry to match
        ``ttl``), exactly what the encoder's deterministic-key dedup needs.

        Args:
            key: Unique identifier for the data.
            data: JSON-serializable dictionary to store.
            ttl: Time-to-live in seconds (``None`` = no expiration; the key is
                persistent). The server enforces the expiry.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the write fails.
        """
        self._ensure_open()
        try:
            await self._client.set(self._k(key), json.dumps(data, separators=(",", ":")), ex=ttl)
        except RedisError as exc:
            raise StorageError(f"Failed to set key {key!r}: {exc}") from exc

    async def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve the value stored under ``key``.

        Expired keys are absent server-side, so this returns ``None`` for them
        without raising.

        Args:
            key: Unique identifier for the data.

        Returns:
            A fresh dictionary parsed from storage, or ``None`` if the key is
            missing or expired.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the read fails.
        """
        self._ensure_open()
        try:
            raw = await self._client.get(self._k(key))
        except RedisError as exc:
            raise StorageError(f"Failed to get key {key!r}: {exc}") from exc

        if raw is None:
            return None
        # json.loads accepts both str and bytes; it returns a fresh dict, so the
        # stored value is naturally isolated from callers.
        return cast("dict[str, Any]", json.loads(raw))

    async def delete(self, key: str) -> bool:
        """Delete the value stored under ``key``.

        Args:
            key: Unique identifier for the data.

        Returns:
            ``True`` if a key was removed, ``False`` if it did not exist.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the delete fails.
        """
        self._ensure_open()
        try:
            return bool(await self._client.delete(self._k(key)))
        except RedisError as exc:
            raise StorageError(f"Failed to delete key {key!r}: {exc}") from exc

    async def exists(self, key: str) -> bool:
        """Check whether ``key`` exists (and has not expired).

        Args:
            key: Unique identifier to check.

        Returns:
            ``True`` if the key exists server-side.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the read fails.
        """
        self._ensure_open()
        try:
            return bool(await self._client.exists(self._k(key)))
        except RedisError as exc:
            raise StorageError(f"Failed to check existence of key {key!r}: {exc}") from exc

    async def clear(self) -> None:
        """Delete every key in this store's namespace.

        Implemented with a namespace-scoped ``SCAN MATCH`` followed by ``DELETE``;
        it NEVER issues ``FLUSHDB``, so other namespaces sharing the same
        server/database are left untouched.

        Warning:
            This removes ALL callbacks stored under this namespace. Use with care
            in production.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the operation fails.
        """
        self._ensure_open()
        try:
            keys = [k async for k in self._scan(f"{self._ns}*")]
            if keys:
                await self._client.delete(*keys)
        except RedisError as exc:
            raise StorageError(f"Failed to clear storage: {exc}") from exc

    async def keys(self, pattern: str | None = None) -> list[str]:
        """Return the namespace's keys, optionally filtered by a glob pattern.

        The pattern is applied via ``SCAN MATCH`` and the namespace prefix is
        stripped from the results so callers see the keys they supplied.

        Note:
            ``SCAN MATCH`` uses Redis/Valkey glob syntax, which differs from
            Python's :mod:`fnmatch` (used by ``MemoryStorage``): character-class
            negation is written ``[^...]`` here rather than ``[!...]``.

        Args:
            pattern: Optional glob pattern (without the namespace prefix).

        Returns:
            A list of matching keys with the namespace prefix removed.

        Raises:
            RuntimeError: If the storage is closed.
            StorageError: If the read fails.
        """
        self._ensure_open()
        match = f"{self._ns}{pattern}" if pattern is not None else f"{self._ns}*"
        try:
            found = [k async for k in self._scan(match)]
        except RedisError as exc:
            raise StorageError(f"Failed to list keys: {exc}") from exc

        return [k.removeprefix(self._ns) for k in found]

    async def close(self) -> None:
        """Close the storage, closing the client only if it is owned.

        A borrowed client (supplied via ``client=``) is left open so the caller
        can keep using it.
        """
        if self._closed:
            return
        if self._owns_client:
            await self._client.aclose()
        await super().close()
