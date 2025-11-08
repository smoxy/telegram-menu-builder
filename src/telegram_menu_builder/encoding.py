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
        """Encode data inline with compression.

        Args:
            data: Data dictionary to encode

        Returns:
            Encoded string or None if too large
        """
        try:
            # Serialize to JSON with minimal separators
            json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
            json_bytes = json_str.encode("utf-8")

            # Try compression
            compressed = zlib.compress(json_bytes, level=9)

            # Use the smaller of compressed vs uncompressed
            to_encode = compressed if len(compressed) < len(json_bytes) else json_bytes
            use_compression = len(compressed) < len(json_bytes)

            # Base64 encode
            b64_encoded = base64.b64encode(to_encode).decode("ascii")

            # Add prefix with compression flag
            prefix = "IC:" if use_compression else self.PREFIX_INLINE
            result = f"{prefix}{b64_encoded}"

            # Check size
            if len(result) <= 64:
                return result

            return None

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
            # Determine if compressed
            if encoded.startswith("IC:"):
                use_compression = True
                b64_str = encoded[3:]
            elif encoded.startswith(self.PREFIX_INLINE):
                use_compression = False
                b64_str = encoded[2:]
            else:
                raise DecodingError("Invalid inline encoding prefix")

            # Base64 decode
            decoded_bytes = base64.b64decode(b64_str)

            # Decompress if needed
            if use_compression:
                decoded_bytes = zlib.decompress(decoded_bytes)

            # Parse JSON
            json_str = decoded_bytes.decode("utf-8")
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
        # Serialize with sorted keys for determinism
        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        hash_obj = hashlib.md5(json_str.encode("utf-8"))
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
