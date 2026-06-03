# Encoding Internals

This page explains how a `MenuAction` becomes a `callback_data` string and back
again. The logic lives in
[`CallbackEncoder`][telegram_menu_builder.encoding.CallbackEncoder]. You rarely
call it directly — [`MenuBuilder`](../guide/menu-building.md) encodes on
`build()` and [`MenuRouter`](../guide/routing.md) decodes on `route()` — but
understanding it helps you keep callbacks inline and debug decode failures.

## The data dict

Before encoding, a `MenuAction` is reduced to a compact dict with single-letter
keys to save bytes:

```python
data = {
    "h": action.handler,   # handler name
    "p": action.params,    # the params dict
}
```

This `{h, p}` shape is what gets serialized, stored, or compressed. On decode
the encoder reconstructs `MenuAction(handler=data["h"], params=data.get("p", {}))`.

## The 64-byte budget

Telegram caps `callback_data` at 64 bytes. The encoder reserves a little room
for its prefix, so it treats **60 bytes** as the inline threshold and **500
bytes** as the boundary between short-term and persistent storage:

```python
INLINE_THRESHOLD = 60   # 64-byte limit, minus room for the prefix
SHORT_THRESHOLD = 500
```

The strategy is chosen automatically:

| Encoded size | Strategy | Result |
| --- | --- | --- |
| Fits inline (final string ≤ 64 bytes) | Inline | `I:...` or `IC:...` |
| JSON < 500 bytes (didn't fit inline) | Short | `S:<key>` |
| JSON ≥ 500 bytes | Persistent | `P:<key>` |

See [Storage](../guide/storage.md) for what happens to the stored payloads.

## The inline path: zlib + base64

For inline encoding the encoder serializes the data dict to compact JSON
(`separators=(",", ":")`, ASCII), then tries to shrink it with `zlib` at maximum
level and base64-encodes the result:

```python
json_bytes = json.dumps(data, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
compressed = zlib.compress(json_bytes, level=9)

# Pick whichever is smaller — compression has overhead and can grow tiny payloads.
to_encode = compressed if len(compressed) < len(json_bytes) else json_bytes
b64 = base64.b64encode(to_encode).decode("ascii")
prefix = "IC:" if len(compressed) < len(json_bytes) else "I:"
result = f"{prefix}{b64}"
```

The key detail is the **smaller-of-compressed-vs-raw** choice. For very small
payloads zlib's header makes the compressed form *larger* than the original, so
the encoder keeps the raw JSON and marks it `I:`. When compression wins, it uses
`IC:`. If the final string is still ≤ 64 bytes it becomes the callback data;
otherwise the encoder falls back to short/persistent storage.

!!! note "base64 overhead"
    base64 expands bytes by roughly 4/3. Combined with the 2–3 byte prefix, the
    practical inline budget for the *uncompressed* JSON is small — a handler name
    plus a couple of short integer params. Compression buys back room for
    repetitive content (e.g. a breadcrumb of similar strings).

## Deterministic dedup key

Short and persistent payloads are stored under a key derived from the data
itself, so identical actions reuse the same storage slot (deduplication). The
key is the first 12 hex chars of an MD5 over the canonical JSON:

```python
json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
hashlib.md5(json_str.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
```

`sort_keys=True` makes the serialization canonical, so two equal actions always
produce the same key regardless of insertion order.

!!! warning "MD5 here is non-cryptographic"
    MD5 is used purely as a fast, deterministic dedup hash — never for security.
    `usedforsecurity=False` makes that intent explicit and keeps security
    linters quiet (it also allows the hash on FIPS-restricted builds). The keys
    are not secrets and must not be treated as such. See the
    [security notes](../security.md) for the full rationale.

## Estimating size up front

`estimate_encoded_size(action)` gives a rough byte estimate **without** touching
storage. It is handy when you want to decide layout or warn about oversized
params before building:

```python
from telegram_menu_builder.encoding import estimate_encoded_size
from telegram_menu_builder import MenuAction

size = estimate_encoded_size(MenuAction(handler="edit", params={"id": 123}))
```

The estimate assumes ~30% compression and ~33% base64 overhead plus a small
prefix. It is intentionally approximate — the real encoder always measures the
actual encoded string against the 64-byte limit, so treat the estimate as
guidance, not a guarantee.

## Cleaning up short-term entries

After a short-lived callback has been handled, you can free its storage slot
immediately rather than waiting for the TTL to lapse. `cleanup_callback` only
acts on `S:`-prefixed (short) callbacks; persistent (`P:`) and inline (`I:` /
`IC:`) data are left untouched:

```python
@router.after
async def free_short_callbacks(update, context, params):
    data = update.callback_query.data
    if data:
        await router.encoder.cleanup_callback(data)
```

`cleanup_callback` returns `True` when it deleted a short entry and `False`
otherwise (inline/persistent data, missing key, or any error). It is safe to
call on every callback.

!!! note "Inline and persistent data are never cleaned here"
    Inline callbacks carry no storage entry, and persistent callbacks are meant
    to outlive a single interaction, so `cleanup_callback` deliberately ignores
    both.

## See also

- [Storage strategies](../guide/storage.md) — the backends that hold `S:`/`P:`
  payloads.
- [Custom storage backends](custom-storage.md) — implement your own backend.
- [Security notes](../security.md) — why MD5 here is safe.
