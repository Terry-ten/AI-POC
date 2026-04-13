import gc
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from services.http_runtime import create_http_client, send_raw_http
from services.poc_library_service import PocLibraryService


class FakeResponse:
    def __init__(self, text="ok", status_code=200):
        self.text = text
        self.status_code = status_code


class FakeSession:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return FakeResponse()


class TestPocLibraryService(PocLibraryService):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pocs_dir = self.base_dir / "pocs"
        self.db_path = self.pocs_dir / "poc_library.db"
        self.init_storage()
        self.init_database()


class HTTPRuntimeTests(unittest.TestCase):
    def tearDown(self):
        gc.collect()

    def test_create_http_client_applies_defaults(self):
        session = FakeSession()
        client = create_http_client(timeout=9, headers={"X-Test": "1"}, session=session)
        client.get("http://example.com/demo")

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "http://example.com/demo")
        self.assertEqual(kwargs["timeout"], 9)
        self.assertEqual(kwargs["verify"], False)
        self.assertEqual(kwargs["headers"]["X-Test"], "1")
        self.assertIn("User-Agent", kwargs["headers"])

    def test_send_raw_http_parses_response(self):
        class FakeSocket:
            def __init__(self):
                self.sent = b""
                self._chunks = [
                    b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK",
                    b"",
                ]

            def sendall(self, data):
                self.sent += data

            def recv(self, size):
                return self._chunks.pop(0)

            def close(self):
                pass

        with patch("services.http_runtime.socket.create_connection", return_value=FakeSocket()):
            result = send_raw_http("GET / HTTP/1.1\nHost: example.com\n\n", use_ssl=False, timeout=3)

        self.assertEqual(result["status_line"], "HTTP/1.1 200 OK")
        self.assertEqual(result["body"], "OK")
        self.assertEqual(result["host"], "example.com")

    def test_execute_python_poc_supports_http_runtime_helper(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = TestPocLibraryService(Path(temp_dir))
            poc_path = Path(temp_dir) / "pocs" / "python" / "http_runtime_test.py"
            poc_path.write_text(
                """
def scan(url):
    client = create_http_client(timeout=4, headers={"X-Unit": "yes"})
    response = client.get(url)
    return {
        "vulnerable": False,
        "reason": "运行时可用",
        "details": response.text,
    }
""".strip(),
                encoding="utf-8",
            )

            fake_session = FakeSession()
            with patch("services.http_runtime.requests.Session", return_value=fake_session):
                result = service._execute_python_poc(str(poc_path), "http://example.com")

            self.assertTrue(result["success"])
            self.assertEqual(result["result"]["reason"], "运行时可用")
            self.assertEqual(result["result"]["details"], "ok")


if __name__ == "__main__":
    unittest.main()
