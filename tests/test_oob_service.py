import gc
import importlib
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from services.oob_service import CEyeClient, InteractshClient, OOBService, load_interactsh_crypto_backend
from services.poc_library_service import PocLibraryService


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

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if not self.responses:
            raise RuntimeError("no response prepared")
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if not self.responses:
            raise RuntimeError("no response prepared")
        return self.responses.pop(0)


class FakeOOBClient:
    def build_probe(self, protocol="http", length=10, value=""):
        return {"url": "http://unit.test", "flag": "flag1234"}

    def verify(self, flag, protocol="http"):
        return {"matched": True, "events": [{"flag": flag}], "error": None}


class TestPocLibraryService(PocLibraryService):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pocs_dir = self.base_dir / "pocs"
        self.db_path = self.pocs_dir / "poc_library.db"
        self.init_storage()
        self.init_database()


class OOBServiceTests(unittest.TestCase):
    def tearDown(self):
        gc.collect()

    def test_update_config_persists_and_masks_secret(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = OOBService(config_file=Path(temp_dir) / "oob.json")
            service.update_config(
                enabled=True,
                provider="ceye",
                ceye_token="abcdef123456",
                ceye_base_url="http://api.ceye.io/v1",
                poll_interval=2,
                max_polls=5,
            )

            preview = service.get_current_config()
            self.assertTrue(preview["enabled"])
            self.assertEqual(preview["provider"], "ceye")
            self.assertEqual(preview["ceye_token_preview"], "abc...456")
            self.assertEqual(preview["max_polls"], 5)

    def test_ceye_client_can_build_probe_and_verify(self):
        session = FakeSession([
            FakeResponse({"data": {"identify": "demoid"}}),
            FakeResponse({"data": [{"name": "http://flag1234.demonstration.ceye.io"}]}),
        ])

        client = CEyeClient(
            token="token123",
            base_url="http://api.ceye.io/v1",
            session=session,
            sleep_func=lambda _: None,
        )
        probe = client.build_probe(protocol="http", value="hello")
        result = client.verify("flag1234", protocol="http")

        self.assertIn("url", probe)
        self.assertIn("flag", probe)
        self.assertTrue(result["matched"])
        self.assertEqual(len(result["events"]), 1)

    def test_interactsh_crypto_backend_falls_back_to_crypto_namespace(self):
        try:
            importlib.import_module("Crypto.Cipher.AES")
            importlib.import_module("Crypto.Cipher.PKCS1_OAEP")
            importlib.import_module("Crypto.Hash.SHA256")
            importlib.import_module("Crypto.PublicKey.RSA")
        except ImportError:
            self.skipTest("Crypto 命名空间依赖未安装")

        real_import_module = importlib.import_module

        def fake_import_module(name, package=None):
            if name.startswith("Cryptodome."):
                raise ImportError("missing Cryptodome")
            if name in (
                "Crypto.Cipher.AES",
                "Crypto.Cipher.PKCS1_OAEP",
                "Crypto.Hash.SHA256",
                "Crypto.PublicKey.RSA",
            ):
                return real_import_module(name, package)
            return real_import_module(name, package)

        with patch("services.oob_service.importlib.import_module", side_effect=fake_import_module):
            aes, pkcs1_oaep, sha256, rsa = load_interactsh_crypto_backend()

        self.assertTrue(hasattr(aes, "MODE_CFB"))
        self.assertTrue(callable(pkcs1_oaep.new))
        self.assertTrue(callable(sha256.new))
        self.assertTrue(callable(rsa.generate))

    def test_interactsh_verify_handles_null_data_without_exception(self):
        try:
            load_interactsh_crypto_backend()
        except ImportError:
            self.skipTest("Interactsh 依赖未安装")

        session = FakeSession([
            FakeResponse({}, status_code=200),
            FakeResponse({"aes_key": "ignored", "data": None}, status_code=200),
        ])

        client = InteractshClient(
            server="oast.me",
            session=session,
            sleep_func=lambda _: None,
            max_polls=1,
        )

        result = client.verify("flag1234", protocol="dns")

        self.assertFalse(result["matched"])
        self.assertEqual(result["events"], [])

    def test_get_runtime_status_reports_interactsh_dependency_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = OOBService(config_file=Path(temp_dir) / "oob.json")
            service.update_config(enabled=True, provider="interactsh", interactsh_server="oast.me")

            with patch("services.oob_service.load_interactsh_crypto_backend", side_effect=ImportError("missing")):
                status = service.get_runtime_status()

            self.assertFalse(status["runtime_ready"])
            self.assertFalse(status["dependency_ready"])
            self.assertIn("Interactsh", status["runtime_error"])

    def test_execute_oob_poc_is_blocked_when_runtime_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = TestPocLibraryService(Path(temp_dir))
            poc_id = service.save_poc(
                vuln_type="rce",
                vuln_name="Demo OOB Poc",
                vuln_info="demo info",
                poc_code="def scan(url):\n    return {'vulnerable': False, 'reason': 'should not run', 'details': {}}\n",
                explanation="demo",
                verifiable=True,
                execution_mode="url_only",
                verification_method="oob",
            )

            with patch("services.poc_library_service.oob_service.get_runtime_status", return_value={
                "enabled": True,
                "provider": "interactsh",
                "dependency_ready": False,
                "dependency_error": "Interactsh 依赖未安装，请安装 pycryptodome 或 pycryptodomex",
                "runtime_ready": False,
                "runtime_error": "Interactsh 依赖未安装，请安装 pycryptodome 或 pycryptodomex",
            }):
                result = service.execute_poc(poc_id, "http://example.com")

            self.assertFalse(result["success"])
            self.assertIn("Interactsh", result["error"])
            self.assertIn("OOB 运行环境不可用", result["result"]["reason"])

    def test_execute_python_poc_supports_oob_runtime_helper(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = TestPocLibraryService(Path(temp_dir))
            poc_path = Path(temp_dir) / "pocs" / "python" / "oob_test.py"
            poc_path.write_text(
                """
def scan(url):
    client = get_oob_client()
    probe = client.build_probe()
    verification = client.verify(probe["flag"])
    return {
        "vulnerable": verification["matched"],
        "reason": "OOB命中" if verification["matched"] else "未命中",
        "details": verification["events"],
    }
""".strip(),
                encoding="utf-8",
            )

            with patch("services.poc_library_service.oob_service.create_client", return_value=FakeOOBClient()):
                result = service._execute_python_poc(str(poc_path), "http://example.com")

            self.assertTrue(result["success"])
            self.assertTrue(result["result"]["vulnerable"])
            self.assertEqual(result["result"]["reason"], "OOB命中")


if __name__ == "__main__":
    unittest.main()
