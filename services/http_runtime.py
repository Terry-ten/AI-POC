"""
统一 HTTP Runtime

目标：
1. 给新生成 POC 提供统一 HTTP helper
2. 保持旧 requests 脚本继续兼容
3. 预留原始 HTTP 报文重放能力
"""

from __future__ import annotations

import json
import socket
import ssl
from dataclasses import dataclass, field
from typing import Dict, Optional

import requests


DEFAULT_HEADERS = {
    "User-Agent": "AI-POC/1.0",
}


@dataclass
class HTTPRuntimeClient:
    timeout: int = 6
    verify: bool = False
    allow_redirects: bool = True
    headers: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HEADERS))
    session: requests.Session = field(default_factory=requests.Session)

    def request(self, method: str, url: str, **kwargs):
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}) or {})
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("verify", self.verify)
        kwargs.setdefault("allow_redirects", self.allow_redirects)
        kwargs["headers"] = headers
        return self.session.request(method=method.upper(), url=url, **kwargs)

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def raw_request(self, raw: str, use_ssl: bool = False, timeout: Optional[int] = None):
        return send_raw_http(
            raw=raw,
            use_ssl=use_ssl,
            timeout=timeout or self.timeout,
        )


def create_http_client(
    timeout: int = 6,
    verify: bool = False,
    allow_redirects: bool = True,
    headers: Optional[Dict[str, str]] = None,
    session: Optional[requests.Session] = None,
) -> HTTPRuntimeClient:
    resolved_headers = dict(DEFAULT_HEADERS)
    resolved_headers.update(headers or {})
    return HTTPRuntimeClient(
        timeout=timeout,
        verify=verify,
        allow_redirects=allow_redirects,
        headers=resolved_headers,
        session=session or requests.Session(),
    )


def get_http_client() -> HTTPRuntimeClient:
    return create_http_client()


def http_request(method: str, url: str, **kwargs):
    return get_http_client().request(method, url, **kwargs)


def _extract_headers(text: str) -> Dict[str, str]:
    headers = {}
    for line in text.split("\n"):
        if not line.strip():
            continue
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        headers[key.strip()] = value.strip()
    return headers


def send_raw_http(raw: str, use_ssl: bool = False, timeout: int = 6) -> Dict[str, object]:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("原始HTTP请求不能为空")

    lines = [line.rstrip("\r") for line in raw.splitlines()]
    try:
        method, path, _ = lines[0].split(" ", 2)
    except ValueError as exc:
        raise ValueError("原始HTTP请求首行格式错误") from exc

    body = ""
    blank_index = None
    for index, line in enumerate(lines[1:], start=1):
        if not line.strip():
            blank_index = index
            break

    if blank_index is None:
        header_lines = lines[1:]
    else:
        header_lines = lines[1:blank_index]
        body = "\r\n".join(lines[blank_index + 1:])

    headers = _extract_headers("\n".join(header_lines))
    host = headers.get("Host")
    if not host:
        raise ValueError("原始HTTP请求缺少 Host 头")

    if ":" in host:
        hostname, port_text = host.rsplit(":", 1)
        port = int(port_text)
    else:
        hostname = host
        port = 443 if use_ssl else 80

    request_text = raw.replace("\n", "\r\n")
    if not request_text.endswith("\r\n\r\n") and body == "":
        request_text += "\r\n\r\n"

    sock = socket.create_connection((hostname, port), timeout=timeout)
    try:
        if use_ssl:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname=hostname)

        sock.sendall(request_text.encode("utf-8"))
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
        raw_response = b"".join(chunks)
    finally:
        sock.close()

    try:
        text = raw_response.decode("utf-8")
    except UnicodeDecodeError:
        text = raw_response.decode("latin1", errors="replace")

    return {
        "method": method,
        "host": hostname,
        "port": port,
        "path": path,
        "raw_response": text,
        "status_line": text.splitlines()[0] if text else "",
        "body": text.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in text else "",
    }
