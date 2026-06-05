from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Iterator, Mapping, MutableMapping
from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ginext import Gio, GLib, Soup


def _bytes_value(value: bytes | GLib.Bytes) -> bytes:
    if isinstance(value, GLib.Bytes):
        return bytes(value.get_data() or b"")
    return bytes(value)


def _coerce_body(content: bytes | str | GLib.Bytes | None) -> bytes | None:
    if content is None:
        return None
    if isinstance(content, GLib.Bytes):
        return _bytes_value(content)
    if isinstance(content, str):
        return content.encode("utf-8")
    return bytes(content)


def _merge_query_params(
    url: str, params: Mapping[str, object] | Iterable[tuple[str, object]] | None
) -> str:
    if params is None:
        return url
    split = urlsplit(url)
    query = list(parse_qsl(split.query, keep_blank_values=True))
    if isinstance(params, Mapping):
        query.extend((key, str(value)) for key, value in params.items())
    else:
        query.extend((key, str(value)) for key, value in params)
    return urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(query), split.fragment)
    )


def _status_code(message: Soup.Message) -> int:
    return int(message.get_status())


def _reason_phrase(message: Soup.Message) -> str:
    return str(message.get_reason_phrase() or "")


def _message_url(message: Soup.Message) -> str:
    uri = message.get_uri()
    return "" if uri is None else str(uri.to_string())


def _raise_for_status(message: Soup.Message) -> None:
    status_code = _status_code(message)
    if 200 <= status_code < 300:
        return
    raise RuntimeError(f"{status_code} {_reason_phrase(message)}".strip())


class Headers(MutableMapping[str, str]):
    """Mapping view over ``Soup.MessageHeaders`` with dict-like access."""

    def __init__(self, headers: Soup.MessageHeaders) -> None:
        self._headers = headers

    @classmethod
    def from_value(
        cls,
        value: Soup.MessageHeaders
        | Mapping[str, str]
        | Iterable[tuple[str, str]]
        | None,
        *,
        header_type: Soup.MessageHeadersType,
    ) -> Headers:
        if isinstance(value, Soup.MessageHeaders):
            return cls(value)
        headers = Soup.MessageHeaders.new(header_type)
        wrapper = cls(headers)
        if value is not None:
            wrapper.update(value)
        return wrapper

    @property
    def raw(self) -> Soup.MessageHeaders:
        return self._headers

    def get_list(self, name: str) -> list[str]:
        value = self._headers.get_list(name)
        if value is None:
            return []
        return [item.strip() for item in value.split(",")]

    def multi_items(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        self._headers.foreach(lambda name, value: items.append((name, value)))
        return items

    def __getitem__(self, key: str) -> str:
        value = self._headers.get_one(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: str) -> None:
        self._headers.replace(key, value)

    def __delitem__(self, key: str) -> None:
        if self._headers.get_one(key) is None:
            raise KeyError(key)
        self._headers.remove(key)

    def __iter__(self) -> Iterator[str]:
        seen: set[str] = set()
        for name, _value in self.multi_items():
            if name not in seen:
                seen.add(name)
                yield name

    def __len__(self) -> int:
        return len(list(iter(self)))


@dataclass(slots=True)
class Request:
    """High-level HTTP request wrapper around ``Soup.Message``."""

    message: Soup.Message
    headers: Headers
    content: bytes = b""

    def __init__(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
        content: bytes | str | GLib.Bytes | None = None,
        params: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
    ) -> None:
        message = Soup.Message.new(method, _merge_query_params(url, params))
        if message is None:
            raise ValueError(f"failed to create Soup.Message for {method} {url}")
        self.message = message
        self.headers = Headers.from_value(
            message.get_request_headers(),
            header_type=Soup.MessageHeadersType.REQUEST,
        )
        if headers is not None:
            self.headers.update(headers)
        body = _coerce_body(content)
        if body is None:
            self.content = b""
            return
        self.content = body
        content_type = self.headers.get("Content-Type")
        self.message.set_request_body_from_bytes(content_type, body)

    @property
    def method(self) -> str:
        return str(self.message.get_method())

    @property
    def url(self) -> str:
        uri = self.message.get_uri()
        return "" if uri is None else str(uri.to_string())


@dataclass(slots=True)
class Response:
    """Buffered HTTP response with the full body already in memory."""

    request: Request
    message: Soup.Message
    content: bytes
    headers: Headers

    @property
    def status_code(self) -> int:
        return _status_code(self.message)

    @property
    def reason_phrase(self) -> str:
        return _reason_phrase(self.message)

    @property
    def url(self) -> str:
        return _message_url(self.message)

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        return json.loads(self.content.decode("utf-8"))

    def read(self) -> bytes:
        return self.content

    async def aread(self) -> bytes:
        return self.content

    def raise_for_status(self) -> None:
        _raise_for_status(self.message)


@dataclass(slots=True)
class StreamResponse:
    """Streaming HTTP response backed by a native ``Gio.InputStream``."""

    request: Request
    message: Soup.Message
    stream: Gio.InputStream
    headers: Headers
    _closed: bool = False

    async def __aenter__(self) -> StreamResponse:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        await self.aclose()
        return False

    @property
    def status_code(self) -> int:
        return _status_code(self.message)

    @property
    def reason_phrase(self) -> str:
        return _reason_phrase(self.message)

    @property
    def url(self) -> str:
        return _message_url(self.message)

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    async def read(
        self,
        count: int = -1,
        *,
        io_priority: int = GLib.PRIORITY_DEFAULT,
        cancellable: Gio.Cancellable | None = None,
    ) -> bytes:
        """Read up to ``count`` bytes, or the rest of the stream when omitted."""
        if self._closed:
            raise RuntimeError("stream response is closed")
        if count < 0:
            return await self.aread(
                io_priority=io_priority,
                cancellable=cancellable,
            )
        if count == 0:
            return b""
        data = await self.stream.read_bytes_async(
            count,
            io_priority,
            cancellable,
        )
        return _bytes_value(data)

    async def aread(
        self,
        *,
        chunk_size: int = 65536,
        io_priority: int = GLib.PRIORITY_DEFAULT,
        cancellable: Gio.Cancellable | None = None,
    ) -> bytes:
        """Read the remaining response body into memory."""
        parts: list[bytes] = []
        async for chunk in self.iter_bytes(
            chunk_size=chunk_size,
            io_priority=io_priority,
            cancellable=cancellable,
        ):
            parts.append(chunk)
        return b"".join(parts)

    async def iter_bytes(
        self,
        *,
        chunk_size: int = 65536,
        io_priority: int = GLib.PRIORITY_DEFAULT,
        cancellable: Gio.Cancellable | None = None,
    ) -> AsyncIterator[bytes]:
        """Yield the body as chunks from the underlying input stream."""
        while True:
            chunk = await self.read(
                chunk_size,
                io_priority=io_priority,
                cancellable=cancellable,
            )
            if not chunk:
                break
            yield chunk

    async def splice(
        self,
        output_stream: Gio.OutputStream,
        *,
        flags: Gio.OutputStreamSpliceFlags = Gio.OutputStreamSpliceFlags.CLOSE_SOURCE,
        io_priority: int = GLib.PRIORITY_DEFAULT,
        cancellable: Gio.Cancellable | None = None,
    ) -> int:
        """Splice the response body into another native output stream."""
        if self._closed:
            raise RuntimeError("stream response is closed")
        return await output_stream.splice_async(
            self.stream,
            flags,
            io_priority,
            cancellable,
        )

    async def aclose(self) -> None:
        """Close the underlying response body stream."""
        if self._closed:
            return
        self._closed = True
        await self.stream.close_async(GLib.PRIORITY_DEFAULT)

    def raise_for_status(self) -> None:
        _raise_for_status(self.message)


class _StreamContextManager:
    def __init__(self, opener: Callable[[], Awaitable[StreamResponse]]) -> None:
        self._opener = opener
        self._response: StreamResponse | None = None

    async def __aenter__(self) -> StreamResponse:
        response = await self._opener()
        self._response = response
        return response

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        response = self._response
        self._response = None
        if response is not None:
            await response.aclose()
        return False


def _make_response(request: Request, body: bytes | GLib.Bytes) -> Response:
    data = _bytes_value(body)
    return Response(
        request=request,
        message=request.message,
        content=data,
        headers=Headers.from_value(
            request.message.get_response_headers(),
            header_type=Soup.MessageHeadersType.RESPONSE,
        ),
    )


def _make_stream_response(request: Request, stream: Gio.InputStream) -> StreamResponse:
    return StreamResponse(
        request=request,
        message=request.message,
        stream=stream,
        headers=Headers.from_value(
            request.message.get_response_headers(),
            header_type=Soup.MessageHeadersType.RESPONSE,
        ),
    )


def _request_from_session(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
    content: bytes | str | GLib.Bytes | None = None,
    params: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
) -> Request:
    return Request(
        method,
        url,
        headers=headers,
        content=content,
        params=params,
    )


async def _session_send(
    session: Soup.Session,
    request: Request,
    *,
    io_priority: int,
    cancellable: Gio.Cancellable | None,
) -> Response:
    """Send a prepared request and return a buffered response."""
    body = await session.send_and_read_async(
        request.message,
        io_priority,
        cancellable,
    )
    return _make_response(request, body)


async def _session_open_stream(
    session: Soup.Session,
    request: Request,
    *,
    io_priority: int,
    cancellable: Gio.Cancellable | None,
) -> StreamResponse:
    """Send a prepared request and return a streaming response."""
    stream = await session.send_async(
        request.message,
        io_priority,
        cancellable,
    )
    return _make_stream_response(request, stream)


async def _session_request(
    session: Soup.Session,
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
    content: bytes | str | GLib.Bytes | None = None,
    params: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
    io_priority: int = GLib.PRIORITY_DEFAULT,
    cancellable: Gio.Cancellable | None = None,
) -> Response:
    """Build and send a request with a buffered response body."""
    request = _request_from_session(
        method,
        url,
        headers=headers,
        content=content,
        params=params,
    )
    return await _session_send(
        session,
        request,
        io_priority=io_priority,
        cancellable=cancellable,
    )


def _session_stream(
    session: Soup.Session,
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
    content: bytes | str | GLib.Bytes | None = None,
    params: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
    io_priority: int = GLib.PRIORITY_DEFAULT,
    cancellable: Gio.Cancellable | None = None,
) -> _StreamContextManager:
    """Open a streaming request as an async context manager."""
    async def open_stream() -> StreamResponse:
        request = _request_from_session(
            method,
            url,
            headers=headers,
            content=content,
            params=params,
        )
        return await _session_open_stream(
            session,
            request,
            io_priority=io_priority,
            cancellable=cancellable,
        )

    return _StreamContextManager(open_stream)


async def _session_get(
    session: Soup.Session,
    url: str,
    *,
    headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
    params: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
    io_priority: int = GLib.PRIORITY_DEFAULT,
    cancellable: Gio.Cancellable | None = None,
) -> Response:
    """Send a GET request and buffer the response body."""
    return await _session_request(
        session,
        "GET",
        url,
        headers=headers,
        params=params,
        io_priority=io_priority,
        cancellable=cancellable,
    )


async def _session_post(
    session: Soup.Session,
    url: str,
    *,
    headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
    content: bytes | str | GLib.Bytes | None = None,
    params: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
    io_priority: int = GLib.PRIORITY_DEFAULT,
    cancellable: Gio.Cancellable | None = None,
) -> Response:
    """Send a POST request and buffer the response body."""
    return await _session_request(
        session,
        "POST",
        url,
        headers=headers,
        content=content,
        params=params,
        io_priority=io_priority,
        cancellable=cancellable,
    )


class AsyncClient:
    """Convenience wrapper around ``Soup.Session`` with an ``httpx``-like shape.

    Use ``AsyncClient`` when you want default headers, a base URL, and request
    helpers such as ``get()``, ``post()``, and ``stream()`` while still working
    with a real native ``Soup.Session`` underneath.
    """

    def __init__(
        self,
        *,
        base_url: str = "",
        headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
        session: Soup.Session | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._default_headers = dict(headers or {})
        self._session = session if session is not None else Soup.Session()
        self._owns_session = session is None
        self._closed = False

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        await self.aclose()
        return False

    def _resolve_url(self, url: str) -> str:
        if "://" in url or not self._base_url:
            return url
        if url.startswith("/"):
            return f"{self._base_url}{url}"
        return f"{self._base_url}/{url}"

    def build_request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
        content: bytes | str | GLib.Bytes | None = None,
        params: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
    ) -> Request:
        """Build a reusable request with the client's base URL and headers."""
        merged_headers = dict(self._default_headers)
        if headers is not None:
            merged_headers.update(dict(headers))
        return Request(
            method,
            self._resolve_url(url),
            headers=merged_headers,
            content=content,
            params=params,
        )

    @property
    def session(self) -> Soup.Session:
        return self._session

    async def send(
        self,
        request: Request,
        *,
        io_priority: int = GLib.PRIORITY_DEFAULT,
        cancellable: Gio.Cancellable | None = None,
    ) -> Response:
        """Send a prepared request and buffer the full response body."""
        if self._closed:
            raise RuntimeError("Soup.AsyncClient is closed")
        return await _session_send(
            self._session,
            request,
            io_priority=io_priority,
            cancellable=cancellable,
        )

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
        content: bytes | str | GLib.Bytes | None = None,
        params: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
        io_priority: int = GLib.PRIORITY_DEFAULT,
        cancellable: Gio.Cancellable | None = None,
    ) -> _StreamContextManager:
        """Open a streaming response as an async context manager."""
        async def open_stream() -> StreamResponse:
            request = self.build_request(
                method,
                url,
                headers=headers,
                content=content,
                params=params,
            )
            return await _session_open_stream(
                self._session,
                request,
                io_priority=io_priority,
                cancellable=cancellable,
            )

        return _StreamContextManager(open_stream)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
        content: bytes | str | GLib.Bytes | None = None,
        params: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
        io_priority: int = GLib.PRIORITY_DEFAULT,
        cancellable: Gio.Cancellable | None = None,
    ) -> Response:
        """Build and send a request in one call."""
        request = self.build_request(
            method,
            url,
            headers=headers,
            content=content,
            params=params,
        )
        return await self.send(
            request,
            io_priority=io_priority,
            cancellable=cancellable,
        )

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
        params: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
        io_priority: int = GLib.PRIORITY_DEFAULT,
        cancellable: Gio.Cancellable | None = None,
    ) -> Response:
        """Send a GET request and buffer the response body."""
        return await self.request(
            "GET",
            url,
            headers=headers,
            params=params,
            io_priority=io_priority,
            cancellable=cancellable,
        )

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
        content: bytes | str | GLib.Bytes | None = None,
        params: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
        io_priority: int = GLib.PRIORITY_DEFAULT,
        cancellable: Gio.Cancellable | None = None,
    ) -> Response:
        """Send a POST request and buffer the response body."""
        return await self.request(
            "POST",
            url,
            headers=headers,
            content=content,
            params=params,
            io_priority=io_priority,
            cancellable=cancellable,
        )

    async def aclose(self) -> None:
        """Release the owned session by aborting outstanding native work."""
        if self._closed:
            return
        self._closed = True
        if self._owns_session:
            self._session.abort()


def apply_to_namespace(namespace: Any) -> None:
    namespace.__dict__["AsyncClient"] = AsyncClient
    namespace.__dict__["Headers"] = Headers
    namespace.__dict__["Request"] = Request
    namespace.__dict__["Response"] = Response
    namespace.__dict__["StreamResponse"] = StreamResponse
    namespace.Session.request = _session_request
    namespace.Session.get = _session_get
    namespace.Session.post = _session_post
    namespace.Session.stream = _session_stream
