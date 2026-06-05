from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import asyncio
import json
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Coroutine


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/stream"):
            payload = b"streaming-body"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        payload = json.dumps(
            {
                "method": self.command,
                "path": self.path,
                "x_test": self.headers.get("X-Test"),
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Reply", "ok")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        payload = json.dumps(
            {
                "method": self.command,
                "path": self.path,
                "body": body.decode("utf-8"),
                "content_type": self.headers.get("Content-Type"),
            }
        ).encode("utf-8")
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, message: str, *args: object) -> None:
        return


def _run(coro: "Coroutine[object, object, None]") -> None:
    from ginext import aio

    asyncio.run(coro, loop_factory=aio.EventLoop)


def _server_url(server: ThreadingHTTPServer) -> str:
    host = str(server.server_address[0])
    port = int(server.server_address[1])
    return f"http://{host}:{port}"


def _serve_forever(server: ThreadingHTTPServer) -> None:
    server.serve_forever(poll_interval=0.01)


def test_async_client_get() -> None:
    import ginext

    ginext.private.require_namespace("Soup", "3.0")
    from ginext import Soup

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=_serve_forever, args=(server,), daemon=True)
    thread.start()
    try:
        async def main() -> None:
            async with Soup.AsyncClient(headers={"X-Test": "client"}) as client:
                response = await client.get(
                    f"{_server_url(server)}/hello",
                    params={"page": 2},
                )
                assert response.status_code == 200
                assert response.is_success is True
                assert response.headers["X-Reply"] == "ok"
                assert response.request.method == "GET"
                assert response.request.url.endswith("/hello?page=2")
                assert response.url.endswith("/hello?page=2")
                assert response.json() == {
                    "method": "GET",
                    "path": "/hello?page=2",
                    "x_test": "client",
                }

        _run(main())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_async_client_post_and_request_headers() -> None:
    import ginext

    ginext.private.require_namespace("Soup", "3.0")
    from ginext import Soup

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=_serve_forever, args=(server,), daemon=True)
    thread.start()
    try:
        request = Soup.Request(
            "POST",
            f"{_server_url(server)}/submit",
            headers={"Content-Type": "text/plain", "X-Test": "request"},
            content="payload",
        )
        assert request.headers["Content-Type"] == "text/plain"
        assert request.headers.get_list("X-Test") == ["request"]

        async def main() -> None:
            async with Soup.AsyncClient() as client:
                response = await client.send(request)
                assert response.status_code == 201
                assert response.request.content == b"payload"
                assert response.json() == {
                    "method": "POST",
                    "path": "/submit",
                    "body": "payload",
                    "content_type": "text/plain",
                }

        _run(main())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_session_get_and_stream() -> None:
    import ginext

    ginext.private.require_namespace("Soup", "3.0")
    from ginext import Soup

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=_serve_forever, args=(server,), daemon=True)
    thread.start()
    try:
        async def main() -> None:
            session = Soup.Session()
            response = await session.get(f"{_server_url(server)}/hello")
            assert response.status_code == 200
            assert response.json()["path"] == "/hello"

            async with session.stream("GET", f"{_server_url(server)}/stream") as streamed:
                assert streamed.status_code == 200
                assert streamed.headers["Content-Type"] == "application/octet-stream"
                assert await streamed.read(5) == b"strea"
                assert await streamed.read(4) == b"ming"
                assert await streamed.aread() == b"-body"

        _run(main())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_native_session_async_methods_work_directly() -> None:
    import ginext

    ginext.private.require_namespace("Soup", "3.0")
    from ginext import Soup
    from ginext import aio

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=_serve_forever, args=(server,), daemon=True)
    thread.start()
    try:
        async def main() -> None:
            session = Soup.Session()
            message = Soup.Message.new("GET", f"{_server_url(server)}/hello")
            assert message is not None

            body = await session.send_and_read_async(message, 0)
            assert b'"path": "/hello"' in body

            message2 = Soup.Message.new("GET", f"{_server_url(server)}/stream")
            assert message2 is not None
            stream = await session.send_async(message2, 0)
            data = await stream.read_bytes_async(32, 0)
            assert data == b"streaming-body"
            await stream.close_async(0)

        asyncio.run(main(), loop_factory=aio.EventLoop)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
