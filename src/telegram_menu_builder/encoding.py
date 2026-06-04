"""Callback data encoding and decoding utilities.

This module handles the intelligent encoding and decoding of callback data,
automatically selecting the best storage strategy based on data size.
"""

import base64
import hashlib
import json
import zlib
from typing import Any

from telegram_menu_builder.storage.base import StorageBackend
from telegram_menu_builder.types import (
    DecodingError,
    EncodingError,
    MenuAction,
    StorageStrategy,
)


class CallbackEncoder:
    """Handles encoding and decoding of callback data with intelligent compression.

    This class implements a hybrid approach:
    - Small data (< 60 bytes): Inline in callback_data
    - Medium data (60-500 bytes): Temporary storage with reference
    - Large data (> 500 bytes): Persistent storage with reference

    Attributes:
        storage: Storage backend for non-inline data
        prefix_inline: Prefix for inline data ('I:')
        prefix_short: Prefix for short-term storage ('S:')
        prefix_persistent: Prefix for persistent storage ('P:')

    Example:
        >>> encoder = CallbackEncoder(storage)
        >>> action = MenuAction(handler="test", params={"id": 123})
        >>> encoded = await encoder.encode(action)
        >>> decoded = await encoder.decode(encoded)
    """

    # Constants for size thresholds (in bytes)
    INLINE_THRESHOLD = 60  # Telegram callback_data is 64 bytes, leave 4 for prefix
    SHORT_THRESHOLD = 500

    # Prefixes for different storage strategies
    PREFIX_INLINE = "I:"
    PREFIX_INLINE_COMPRESSED = "IC:"
    PREFIX_SHORT = "S:"
    PREFIX_PERSISTENT = "P:"

    def __init__(self, storage: StorageBackend) -> None:
        """Initialize encoder with storage backend.

        Args:
            storage: Storage backend for non-inline data
        """
        self.storage = storage

    async def encode(
        self, action: MenuAction, force_strategy: StorageStrategy | None = None
    ) -> str:
        """Encode MenuAction into callback_data string.

        Args:
            action: MenuAction to encode
            force_strategy: Force a specific storage strategy (for testing)

        Returns:
            Encoded callback_data string (max 64 bytes)

        Raises:
            EncodingError: If encoding fails
        """
        try:
            # Prepare data structure
            data = {
                "h": action.handler,  # Use short keys to save space
                "p": action.params,
            }

            # Try inline encoding first (unless forced otherwise)
            if force_strategy is None or force_strategy == StorageStrategy.INLINE:
                inline_encoded = self._encode_inline(data)
                if inline_encoded and len(inline_encoded) <= 64:
                    return inline_encoded

            # Determine storage strategy
            json_size = len(json.dumps(data, separators=(",", ":")))

            if force_strategy:
                strategy = force_strategy
            elif json_size < self.SHORT_THRESHOLD:
                strategy = StorageStrategy.SHORT
            else:
                strategy = StorageStrategy.PERSISTENT

            # Store externally and return reference
            key = self._generate_key(data)

            if strategy == StorageStrategy.SHORT:
                await self.storage.set(key, data, ttl=action.ttl)
                return f"{self.PREFIX_SHORT}{key}"
            # PERSISTENT
            await self.storage.set(key, data, ttl=None)
            return f"{self.PREFIX_PERSISTENT}{key}"

        except Exception as e:
            raise EncodingError(f"Failed to encode callback data: {e}") from e

    def encode_inline(self, action: MenuAction) -> str:
        """Encode a MenuAction using only the inline (storage-free) path.

        This is the synchronous counterpart to :meth:`encode`. It builds the same
        ``{"h": handler, "p": params}`` dict and runs *only* the inline strategy
        (JSON -> zlib -> base64). Unlike :meth:`encode`, it never spills to storage
        and performs no ``await``: if the resulting callback_data would not fit
        inline (i.e. it would otherwise require a storage spill), an
        :class:`EncodingError` is raised instead.

        Args:
            action: MenuAction to encode.

        Returns:
            Encoded callback_data string (``I:``/``IC:`` prefix, max 64 bytes).

        Raises:
            EncodingError: If the action does not fit within the 64-byte inline
                budget and would therefore require storage.
        """
        data = {
            "h": action.handler,  # Use short keys to save space
            "p": action.params,
        }

        inline_encoded = self._encode_inline(data)
        if inline_encoded is not None and len(inline_encoded) <= 64:
            return inline_encoded

        json_size = len(json.dumps(data, separators=(",", ":")).encode("utf-8"))
        message = (
            f"Callback for handler {action.handler!r} is {json_size}B encoded and exceeds the "
            "64B inline budget; it would require storage — use build_async() or shrink the params."
        )
        raise EncodingError(message)

    async def decode(self, callback_data: str) -> MenuAction:
        """Decode callback_data string back to MenuAction.

        Args:
            callback_data: Encoded callback_data string

        Returns:
            Decoded MenuAction

        Raises:
            DecodingError: If decoding fails or data not found
        """
        try:
            # Check prefix to determine decoding strategy
            if callback_data.startswith((self.PREFIX_INLINE_COMPRESSED, self.PREFIX_INLINE)):
                data = self._decode_inline(callback_data)
            elif callback_data.startswith(self.PREFIX_SHORT):
                key = callback_data[len(self.PREFIX_SHORT) :]
                stored_data = await self.storage.get(key)
                if stored_data is None:
                    raise DecodingError(f"Callback data expired or not found: {key}")
                data = stored_data
            elif callback_data.startswith(self.PREFIX_PERSISTENT):
                key = callback_data[len(self.PREFIX_PERSISTENT) :]
                stored_data = await self.storage.get(key)
                if stored_data is None:
                    raise DecodingError(f"Callback data not found: {key}")
                data = stored_data
            else:
                raise DecodingError(f"Unknown callback_data format: {callback_data[:10]}...")

            # Reconstruct MenuAction
            return MenuAction(
                handler=data["h"],
                params=data.get("p", {}),
            )

        except Exception as e:
            if isinstance(e, DecodingError):
                raise
            raise DecodingError(f"Failed to decode callback data: {e}") from e

    def _encode_inline(self, data: dict[str, Any]) -> str | None:
        """Encode data inline, preferring the most compact representation.

        Two inline tiers are considered and the smallest one that fits Telegram's
        64-byte ``callback_data`` limit wins:

        - ``I:`` carries the minified, ASCII-safe JSON verbatim (no base64
          overhead). This is the common case for small payloads.
        - ``IC:`` carries zlib-compressed, base64-encoded JSON. It is only used
          when compression actually produces a shorter result than the raw JSON
          (e.g. highly repetitive params).

        Args:
            data: Data dictionary to encode.

        Returns:
            Encoded string, or ``None`` if neither tier fits within 64 bytes.
        """
        try:
            # Serialize to JSON with minimal separators (ASCII-safe for callback_data).
            json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
            json_bytes = json_str.encode("utf-8")

            candidates: list[str] = []

            # Tier 1: raw JSON verbatim (no base64 overhead).
            raw = f"{self.PREFIX_INLINE}{json_str}"
            if len(raw.encode("utf-8")) <= 64:
                candidates.append(raw)

            # Tier 2: zlib + base64, only worthwhile when it beats the raw JSON.
            compressed = zlib.compress(json_bytes, level=9)
            if len(compressed) < len(json_bytes):
                b64_encoded = base64.b64encode(compressed).decode("ascii")
                comp = f"{self.PREFIX_INLINE_COMPRESSED}{b64_encoded}"
                if len(comp.encode("utf-8")) <= 64:
                    candidates.append(comp)

            if not candidates:
                return None
            return min(candidates, key=len)

        except Exception:
            return None

    def _decode_inline(self, encoded: str) -> dict[str, Any]:
        """Decode inline callback data.

        Args:
            encoded: Encoded string

        Returns:
            Decoded data dictionary

        Raises:
            DecodingError: If decoding fails
        """
        try:
            if encoded.startswith(self.PREFIX_INLINE_COMPRESSED):
                # Compressed tier: base64 -> zlib -> JSON.
                b64_str = encoded[len(self.PREFIX_INLINE_COMPRESSED) :]
                decoded_bytes = zlib.decompress(base64.b64decode(b64_str))
                json_str = decoded_bytes.decode("utf-8")
            elif encoded.startswith(self.PREFIX_INLINE):
                # Raw tier: the payload is the minified JSON verbatim.
                json_str = encoded[len(self.PREFIX_INLINE) :]
            else:
                raise DecodingError("Invalid inline encoding prefix")

            result: dict[str, Any] = json.loads(json_str)
            return result

        except Exception as e:
            raise DecodingError(f"Failed to decode inline data: {e}") from e

    def _generate_key(self, data: dict[str, Any]) -> str:
        """Generate deterministic key from data.

        This allows the same data to use the same storage key, enabling deduplication.

        Args:
            data: Data dictionary

        Returns:
            12-character hex hash
        """
        # Serialize with sorted keys for determinism. MD5 is used purely as a
        # fast, deterministic dedup key (not for security), so usedforsecurity is
        # disabled to make that intent explicit and satisfy security linters.
        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        hash_obj = hashlib.md5(json_str.encode("utf-8"), usedforsecurity=False)
        return hash_obj.hexdigest()[:12]

    async def cleanup_callback(self, callback_data: str) -> bool:
        """Cleanup storage for a callback_data reference.

        This should be called after a callback is processed to free storage.
        Only affects SHORT strategy (persistent data is kept).

        Args:
            callback_data: Callback data string

        Returns:
            True if cleaned up, False otherwise
        """
        try:
            if callback_data.startswith(self.PREFIX_SHORT):
                key = callback_data[len(self.PREFIX_SHORT) :]
                return await self.storage.delete(key)
            return False
        except Exception:
            return False


def estimate_encoded_size(action: MenuAction) -> int:
    """Estimate the size of encoded callback data.

    This is useful for determining storage strategy before encoding.

    Args:
        action: MenuAction to estimate

    Returns:
        Estimated size in bytes

    Example:
        >>> action = MenuAction(handler="test", params={"id": 123})
        >>> size = estimate_encoded_size(action)
        >>> print(f"Estimated size: {size} bytes")
    """
    data = {
        "h": action.handler,
        "p": action.params,
    }

    json_str = json.dumps(data, separators=(",", ":"))
    json_bytes = json_str.encode("utf-8")

    # Estimate compressed size (rough approximation)
    # Real compression ratio varies, but this gives a reasonable estimate
    estimated_compressed = len(json_bytes) * 0.7  # Assume 30% compression

    # Base64 adds ~33% overhead
    estimated_b64 = estimated_compressed * 1.33

    # Add prefix (2-3 bytes)
    return int(estimated_b64 + 3)
