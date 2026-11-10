# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Guards for the local Studio server against other web pages in the same browser.

Studio is a loopback service without accounts. A page from another site can still
point the participant's browser at it, either directly (a cross-site request) or
through a hostname that rebinds to 127.0.0.1. This ASGI middleware refuses both
before any route runs:

- the ``Host`` header must name a loopback address (``127.0.0.1``, ``localhost``,
  ``::1``), an explicitly allowed host, or the literal address the connection
  arrived on, with the port the server listens on;
- a state-changing request (anything but GET, HEAD, OPTIONS) that carries an
  ``Origin`` must come from the same origin; without ``Origin``, a ``Referer`` or
  ``Sec-Fetch-Site`` naming another site is refused. Requests with none of these
  headers (command-line clients, test clients) are unchanged;
- the optical JSON routes and the geometry lab's evaluation take only ``application/json``
  bodies up to a byte cap; the routes then read the buffered bytes with ``simcase.reader``
  (``bodies.read_envelope``), which refuses duplicate keys, ``NaN``, ``Infinity``, malformed
  and non-UTF-8 text and accepts a leading UTF-8 byte order mark.

Every response carries a Content-Security-Policy that the shipped pages satisfy.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
OPTICAL_BODY_ROUTES = frozenset({"/api/validate", "/api/mesh", "/api/run", "/api/materials/preview",
                                 "/api/geometry-lab/evaluate"})
OPTICAL_BODY_BYTES = 1 << 20
_DIGITS = re.compile(r"[0-9]{1,20}")  # ASCII only: str.isdigit() accepts "²", which int() refuses


def is_loopback(host: str) -> bool:
    """True for the names and addresses that reach only this machine."""
    name = host.strip("[]").lower()
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


class _InlineScripts(HTMLParser):
    """Collect the text of every ``<script>`` without ``src``, exactly as written."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.blocks: list[str] = []
        self._open = None

    def handle_starttag(self, tag, attrs):
        if tag == "script" and not any(name == "src" for name, _ in attrs):
            self._open = []

    def handle_data(self, data):
        if self._open is not None:
            self._open.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._open is not None:
            self.blocks.append("".join(self._open))
            self._open = None


def inline_scripts(html: str) -> list[str]:
    parser = _InlineScripts()
    parser.feed(html)
    parser.close()
    return parser.blocks


def inline_script_hashes(page: Path) -> list[str]:
    """CSP source expressions for the inline ``<script>`` blocks of a shipped page."""
    # Decode the raw bytes without newline translation, as the browser hashes them:
    # a CRLF copy must not silently break the page.
    blocks = inline_scripts(page.read_bytes().decode("utf-8"))
    return ["'sha256-" + base64.b64encode(hashlib.sha256(b.encode("utf-8")).digest()).decode() + "'"
            for b in blocks]


def content_security_policy(script_hashes) -> str:
    # Inline style attributes are used throughout the pages; scripts are not inline
    # except the hashed classic-editor block, so injected markup cannot run script.
    return "; ".join([
        "default-src 'none'",
        " ".join(["script-src", "'self'", *script_hashes]),
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "connect-src 'self'",
        "font-src 'self'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
        "object-src 'none'",
    ])


def _split_host(value: str):
    """``host[:port]`` -> (lowercase host without brackets, port or None); None if malformed."""
    value = value.strip().lower()
    if not value or any(c in value for c in "/\\@ \t"):
        return None
    if value.startswith("["):
        end = value.find("]")
        if end < 0:
            return None
        name, rest = value[1:end], value[end + 1:]
        if rest and not rest.startswith(":"):
            return None
        port = rest[1:] if rest else None
    elif value.count(":") > 1:
        return None  # an unbracketed IPv6 literal is not a valid Host
    else:
        name, _, port = value.partition(":")
        port = port if ":" in value else None
    if port is not None and not _DIGITS.fullmatch(port):
        return None
    return name, (int(port) if port is not None else None)


def _origin_of(url: str):
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


class StudioGuard:
    """Pure ASGI middleware; see the module docstring."""

    def __init__(self, app, *, csp: str, extra_hosts: set[str]):
        self.app = app
        self.csp = csp.encode("latin-1")
        self.extra_hosts = extra_hosts  # shared with the server; filled by ``--host``

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {}
        for key, value in scope.get("headers", []):
            headers.setdefault(key.decode("latin-1").lower(), value.decode("latin-1"))
        problem = self._check(scope, headers)
        if problem is not None:
            await self._refuse(send, *problem)
            return
        method = scope.get("method", "GET").upper()
        if method == "POST" and scope.get("path") in OPTICAL_BODY_ROUTES:
            body = await self._read_capped(headers, receive)
            if isinstance(body, tuple):
                await self._refuse(send, *body)
                return
            receive = _replay(body, receive)

        async def secured_send(message):
            if message["type"] == "http.response.start":
                extra = self._headers()
                present = {k.lower() for k, _ in message.get("headers", [])}
                message = dict(message)
                message["headers"] = list(message.get("headers", [])) + [h for h in extra if h[0] not in present]
            await send(message)

        await self.app(scope, receive, secured_send)

    def _check(self, scope, headers):
        # Browsers always send Host; only a raw HTTP/1.0 client omits it.
        raw_host = headers.get("host")
        if raw_host is not None:
            host = _split_host(raw_host)
            if host is None:
                return 400, "Studio requests need a valid Host header."
            name, port = host
            server = scope.get("server") or (None, None)
            local = str(server[0]).strip("[]").lower() if server[0] is not None else None
            if name not in LOOPBACK_HOSTS and name not in self.extra_hosts and name != local:
                return 403, ("Studio refuses requests for other host names. Open Studio at "
                             "http://127.0.0.1:<port> or http://localhost:<port>.")
            if server[1] is not None and (port if port is not None else 80) != server[1]:
                return 403, "Studio refuses requests addressed to another port."
        if scope.get("method", "GET").upper() in SAFE_METHODS:
            return None
        expected = "http://" + raw_host.strip().lower() if raw_host is not None else None
        origin = headers.get("origin")
        if origin is not None:
            if expected is None or origin.strip().lower() != expected:
                return 403, "Studio refuses state-changing requests from other web pages (Origin mismatch)."
            return None
        referer = headers.get("referer")
        if referer is not None and (expected is None or _origin_of(referer) != expected):
            return 403, "Studio refuses state-changing requests from other web pages (Referer mismatch)."
        if headers.get("sec-fetch-site", "").lower() in ("cross-site", "same-site"):
            return 403, "Studio refuses state-changing requests from other web pages."
        return None

    async def _read_capped(self, headers, receive):
        media = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media != "application/json":
            return 415, "Studio requests require Content-Type: application/json."
        declared = headers.get("content-length")
        if declared is not None and (not _DIGITS.fullmatch(declared.strip()) or int(declared) > OPTICAL_BODY_BYTES):
            return 413, f"Studio request bodies are limited to {OPTICAL_BODY_BYTES} bytes."
        data = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return 400, "The client disconnected before sending the request body."
            data.extend(message.get("body", b""))
            if len(data) > OPTICAL_BODY_BYTES:
                return 413, f"Studio request bodies are limited to {OPTICAL_BODY_BYTES} bytes."
            if not message.get("more_body", False):
                return bytes(data)

    def _headers(self):
        return [(b"content-security-policy", self.csp),
                (b"x-content-type-options", b"nosniff"),
                (b"x-frame-options", b"DENY"),
                (b"referrer-policy", b"same-origin"),
                (b"cross-origin-resource-policy", b"same-origin")]

    async def _refuse(self, send, status, detail):
        body = json.dumps({"detail": detail}).encode()
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"), *self._headers()]})
        await send({"type": "http.response.body", "body": body})


def _replay(body: bytes, receive):
    """Hand the buffered body to the route once, then defer to the real channel."""
    sent = False

    async def replay():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()
    return replay
