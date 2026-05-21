import gc
import tempfile
import time
import unittest
from pathlib import Path

from services.asset_source_service import AssetSourceService, FofaClient, HunterClient, QuakeClient


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if not self.responses:
            raise RuntimeError("no response prepared")
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if not self.responses:
            raise RuntimeError("no response prepared")
        return self.responses.pop(0)


class AssetSourceServiceTests(unittest.TestCase):
    def tearDown(self):
        gc.collect()

    def test_update_config_persists_and_masks_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AssetSourceService(config_file=Path(temp_dir) / "asset.json")
            service.update_provider_config("fofa", email="demo@example.com", token="abc123456")
            config = service.get_current_config()
            self.assertEqual(config["fofa"]["email_preview"], "de***@example.com")
            self.assertEqual(config["fofa"]["token_preview"], "abc...456")

    def test_fofa_client_normalizes_protocol_and_host(self):
        session = FakeSession([FakeResponse({"results": [["https", "demo.example.com"], ["http", "http://raw.example.com"]]})])
        client = FofaClient("demo@example.com", "token", "https://fofa.info/api/v1", session=session, sleep_func=lambda _: None)
        results = client.search('body="ecshop"', pages=1)
        self.assertEqual(results, ["https://demo.example.com", "http://raw.example.com"])
        self.assertEqual(session.calls[0][1], "https://fofa.info/api/v1/search/all")
        self.assertEqual(session.calls[0][2]["params"]["fields"], "protocol,host")

    def test_fofa_client_accepts_full_search_endpoint(self):
        session = FakeSession([FakeResponse({"results": [["https", "third.example.com"]]})])
        client = FofaClient(
            "demo@example.com",
            "token",
            "https://third-party.example/api/v1/search/all",
            session=session,
            sleep_func=lambda _: None,
        )
        results = client.search('body="ecshop"', pages=1)
        self.assertEqual(results, ["https://third.example.com"])
        self.assertEqual(session.calls[0][1], "https://third-party.example/api/v1/search/all")

    def test_fofa_client_raises_api_error_message(self):
        session = FakeSession([FakeResponse({"error": True, "errmsg": "[820031] F点余额不足"})])
        client = FofaClient("demo@example.com", "token", "https://fofa.info/api/v1", session=session, sleep_func=lambda _: None)
        with self.assertRaisesRegex(RuntimeError, "F点余额不足"):
            client.search('body="ecshop"', pages=1)

    def test_hunter_client_returns_urls(self):
        session = FakeSession([FakeResponse({"code": 200, "data": {"arr": [{"url": "http://hunter.example.com"}]}})])
        client = HunterClient("token", "https://hunter.qianxin.com/openApi/search", session=session, sleep_func=lambda _: None)
        results = client.search('web.title="demo"', pages=1)
        self.assertEqual(results, ["http://hunter.example.com"])

    def test_quake_client_builds_http_targets(self):
        session = FakeSession([FakeResponse({"code": 0, "data": [{"ip": "1.1.1.1", "port": 8080}]})])
        client = QuakeClient("token", "https://quake.360.net/api/v3", session=session, sleep_func=lambda _: None)
        results = client.search('app:"demo"', pages=1)
        self.assertEqual(results, ["http://1.1.1.1:8080"])

    def test_import_targets_uses_selected_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AssetSourceService(
                config_file=Path(temp_dir) / "asset.json",
                provider_factories={"fofa": lambda: type("Client", (), {"search": lambda self, q, pages: ["http://a", "http://b"]})()},
            )
            result = service.import_targets("fofa", 'body="ecshop"', pages=2)
            self.assertEqual(result["provider"], "fofa")
            self.assertEqual(result["total"], 2)
            self.assertEqual(result["targets"], ["http://a", "http://b"])


if __name__ == "__main__":
    unittest.main()
