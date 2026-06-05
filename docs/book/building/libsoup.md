# HTTP with libsoup

> Use `Soup` when you want HTTP in native `ginext`: a real `Soup.Session` for connection/authentication state, plus an `httpx`-shaped async surface for common request and streaming flows.

## What this chapter covers

- `from ginext import Soup` and why `Soup.Session` is the core object.
- Buffered requests with `await session.get(...)` and `await client.get(...)`.
- Streaming responses with `async with client.stream(...) as response:`.
- Request and response helpers: `Headers`, `Request`, `Response`, `StreamResponse`.
- When to use a plain `Session` versus `AsyncClient`.

## Basic usage

Run native async code on ginext's GLib-backed loop:

```python
import asyncio

from ginext import Soup, aio


async def main() -> None:
    response = await Soup.Session().get("https://example.com")
    response.raise_for_status()
    print(response.status_code)
    print(response.text)


asyncio.run(main(), loop_factory=aio.EventLoop)
```

`Soup.Session` is the real libsoup state holder. It owns connection pooling,
authentication state, proxy and timeout settings, and feature objects. Most
applications should keep one session and reuse it.

The lower-level async methods are also awaitable directly in native `ginext`.
If you need the raw libsoup or Gio objects, this works too:

```python
message = Soup.Message.new("GET", "https://example.com/data.json")
assert message is not None

body = await session.send_and_read_async(message, 0)
stream = await session.send_async(message, 0)
chunk = await stream.read_bytes_async(65536, 0)
await stream.close_async(0)
```

For most application code, prefer `session.get(...)`, `session.stream(...)`,
or `Soup.AsyncClient`, since those helpers give you Python-facing request and
response objects with a smaller API to learn.

## httpx-shaped client

If you want a higher-level surface, use `Soup.AsyncClient`:

```python
import asyncio

from ginext import Soup, aio


async def main() -> None:
    async with Soup.AsyncClient(
        base_url="https://example.com",
        headers={"User-Agent": "my-app/1.0"},
    ) as client:
        response = await client.get("/api/items", params={"page": 2})
        response.raise_for_status()
        print(response.json())


asyncio.run(main(), loop_factory=aio.EventLoop)
```

Current `httpx`-style pieces:

- `Soup.AsyncClient`
- `Soup.Request`
- `Soup.Response`
- `Soup.StreamResponse`
- `Soup.Headers`
- `client.request/get/post(...)`
- `client.stream(...)`
- `session.request/get/post(...)`
- `session.stream(...)`

This is intentionally `httpx`-like, not full compatibility.

## Buffered responses

Buffered requests read the whole body into memory first:

```python
response = await session.get("https://example.com/data.json")
response.raise_for_status()

data = response.read()
text = response.text
payload = response.json()
```

Use this when the body is small or you want the simplest API.

## Streaming responses

For large downloads, stream from `Soup.Session.send_async()` instead of loading
the whole body at once:

```python
import asyncio

from ginext import Soup, aio


async def main() -> None:
    session = Soup.Session()

    async with session.stream("GET", "https://example.com/big-file.bin") as response:
        response.raise_for_status()

        async for chunk in response.iter_bytes(chunk_size=65536):
            print("received", len(chunk), "bytes")


asyncio.run(main(), loop_factory=aio.EventLoop)
```

Or read manually:

```python
async with client.stream("GET", url) as response:
    head = await response.read(4096)
    rest = await response.aread()
```

`StreamResponse.aclose()` closes the underlying `Gio.InputStream`; the async
context manager does that automatically.

## Session vs AsyncClient

Use `Soup.Session` when:

- you want the real libsoup object up front
- you need to configure session features or properties
- you want one long-lived HTTP state object

Use `Soup.AsyncClient` when:

- you want a more familiar Python HTTP client shape
- you want `base_url` and default headers
- you still want to inject your own `Soup.Session`

`AsyncClient.session` exposes the underlying native `Soup.Session`.

## Notes

- `client.stream(...)` mirrors `httpx`'s context-manager style.
- `response.raise_for_status()` is available on both buffered and streaming responses.
- Large bodies should prefer the streaming API.
