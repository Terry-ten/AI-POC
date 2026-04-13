import gc
import tempfile
import time
import unittest
from pathlib import Path

from services.poc_library_service import PocLibraryService


class TestPocLibraryService(PocLibraryService):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pocs_dir = self.base_dir / "pocs"
        self.db_path = self.pocs_dir / "poc_library.db"
        self.init_storage()
        self.init_database()


class RuntimeParamsTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._temp_dir.name)
        self.service = TestPocLibraryService(self.base_dir)

    def tearDown(self):
        self.service = None
        gc.collect()
        for _ in range(5):
            try:
                self._temp_dir.cleanup()
                break
            except PermissionError:
                time.sleep(0.1)
        else:
            self.fail("临时测试目录清理失败，数据库文件仍被占用")

    def _write_python_poc(self, name: str, code: str) -> Path:
        path = self.service.pocs_dir / "python" / name
        path.write_text(code, encoding="utf-8")
        return path

    def test_legacy_scan_signature_still_works_with_runtime_params(self):
        poc_path = self._write_python_poc(
            "legacy_scan.py",
            """
def scan(url):
    return {"vulnerable": False, "reason": f"legacy:{url}", "details": ""}
""".strip(),
        )

        result = self.service._execute_python_poc(
            str(poc_path),
            "http://example.com",
            runtime_params={"cookie": "demo=1"},
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["result"]["vulnerable"])
        self.assertIn("legacy:http://example.com/", result["result"]["reason"])

    def test_runtime_params_are_exposed_as_globals(self):
        poc_path = self._write_python_poc(
            "runtime_globals.py",
            """
def scan(url):
    cookie = get_runtime_param("cookie", "")
    return {"vulnerable": bool(cookie), "reason": cookie, "details": runtime_params}
""".strip(),
        )

        result = self.service._execute_python_poc(
            str(poc_path),
            "http://example.com",
            runtime_params={"cookie": "PHPSESSID=test"},
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["result"]["vulnerable"])
        self.assertEqual(result["result"]["reason"], "PHPSESSID=test")
        self.assertEqual(result["result"]["details"]["cookie"], "PHPSESSID=test")

    def test_runtime_params_can_be_passed_as_second_argument(self):
        poc_path = self._write_python_poc(
            "runtime_args.py",
            """
def scan(url, runtime_params):
    token = runtime_params.get("token", "")
    return {"vulnerable": bool(token), "reason": token, "details": {"url": url}}
""".strip(),
        )

        result = self.service._execute_python_poc(
            str(poc_path),
            "http://example.com",
            runtime_params={"token": "abc123"},
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["result"]["vulnerable"])
        self.assertEqual(result["result"]["reason"], "abc123")
        self.assertEqual(result["result"]["details"]["url"], "http://example.com/")


if __name__ == "__main__":
    unittest.main()
