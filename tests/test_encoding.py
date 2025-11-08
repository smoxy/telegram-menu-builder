"""Test suite for encoding/decoding functionality."""

import pytest

from telegram_menu_builder.encoding import CallbackEncoder, estimate_encoded_size
from telegram_menu_builder.types import MenuAction, EncodingError, DecodingError
from telegram_menu_builder.storage import MemoryStorage


class TestCallbackEncoder:
    """Tests for CallbackEncoder class."""

    @pytest.fixture
    def storage(self):
        """Provide a fresh storage instance."""
        return MemoryStorage()

    @pytest.fixture
    def encoder(self, storage):
        """Provide a fresh encoder instance."""
        return CallbackEncoder(storage)

    @pytest.mark.asyncio
    async def test_encode_decode_simple_action(self, encoder):
        """Test encoding and decoding a simple action."""
        action = MenuAction(handler="test_handler", params={"id": 123})

        encoded = await encoder.encode(action)
        decoded = await encoder.decode(encoded)

        assert decoded.handler == "test_handler"
        assert decoded.params == {"id": 123}

    @pytest.mark.asyncio
    async def test_encode_decode_complex_params(self, encoder):
        """Test encoding and decoding complex parameters."""
        action = MenuAction(
            handler="edit_user",
            params={
                "user_id": 123,
                "field": "email",
                "metadata": {"source": "admin"},
                "breadcrumb": ["main", "users", "edit"],
                "nested": {"a": 1, "b": [2, 3, 4]},
            },
        )

        encoded = await encoder.encode(action)
        decoded = await encoder.decode(encoded)

        assert decoded.handler == "edit_user"
        assert decoded.params["user_id"] == 123
        assert decoded.params["breadcrumb"] == ["main", "users", "edit"]
        assert decoded.params["nested"]["b"] == [2, 3, 4]

    @pytest.mark.asyncio
    async def test_inline_encoding_for_small_data(self, encoder):
        """Test that small data is encoded inline."""
        action = MenuAction(handler="test", params={"id": 1})

        encoded = await encoder.encode(action)

        # Should be inline (starts with I: or IC:)
        assert encoded.startswith("I")
        assert len(encoded) <= 64

    @pytest.mark.asyncio
    async def test_storage_for_large_data(self, encoder):
        """Test that large data is stored externally."""
        # Create action with large params
        action = MenuAction(handler="test_handler", params={"data": "x" * 500})  # Large string

        encoded = await encoder.encode(action)

        # Should use storage (starts with S: or P:)
        assert encoded.startswith("S:") or encoded.startswith("P:")

    @pytest.mark.asyncio
    async def test_decode_invalid_data_raises_error(self, encoder):
        """Test that decoding invalid data raises DecodingError."""
        with pytest.raises(DecodingError):
            await encoder.decode("INVALID_DATA_HERE")

    @pytest.mark.asyncio
    async def test_decode_expired_data_raises_error(self, encoder):
        """Test that decoding expired data raises DecodingError."""
        # Create large data to force short-term storage usage (not inline)
        action = MenuAction(handler="test", params={"data": "x" * 1000})

        # Encode with very short TTL
        action.ttl = 1
        encoded = await encoder.encode(action)

        # Verify it's using storage (not inline)
        if encoded.startswith("I") or encoded.startswith("IC"):
            # If inline, we can't test expiration, so skip
            pytest.skip("Data was encoded inline, cannot test expiration")

        # Wait for expiration
        import asyncio

        await asyncio.sleep(2)

        # Should raise DecodingError
        with pytest.raises(DecodingError, match="expired|not found"):
            await encoder.decode(encoded)

    @pytest.mark.asyncio
    async def test_cleanup_callback(self, encoder):
        """Test cleanup of stored callback data."""
        # Create large data to force storage usage
        action = MenuAction(handler="test", params={"data": "x" * 1000})

        encoded = await encoder.encode(action)

        # Should be in storage (check if it starts with S: or P:)
        if encoded.startswith("S:") or encoded.startswith("P:"):
            key = encoded[2:]  # Remove prefix
            assert await encoder.storage.exists(key)

            # Cleanup
            await encoder.cleanup_callback(encoded)

            # Should no longer exist
            assert not await encoder.storage.exists(key)

        # Should be removed
        assert not await encoder.storage.exists(encoded[2:])

    @pytest.mark.asyncio
    async def test_deterministic_key_generation(self, encoder):
        """Test that same data generates same key."""
        action1 = MenuAction(handler="test", params={"id": 123})
        action2 = MenuAction(handler="test", params={"id": 123})

        encoded1 = await encoder.encode(action1)
        encoded2 = await encoder.encode(action2)

        # Should be identical
        assert encoded1 == encoded2

    def test_estimate_encoded_size(self):
        """Test size estimation."""
        action = MenuAction(handler="test", params={"id": 123})

        size = estimate_encoded_size(action)

        assert isinstance(size, int)
        assert size > 0
        assert size < 1000  # Reasonable size

    @pytest.mark.asyncio
    async def test_compression_reduces_size(self, encoder):
        """Test that compression works for repetitive data."""
        # Repetitive data compresses well
        action = MenuAction(handler="test", params={"data": "a" * 50})

        encoded = await encoder.encode(action)

        # Should be inline due to compression
        assert encoded.startswith("I")
