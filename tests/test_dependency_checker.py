import gc
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import api.routes as routes_module
import services.poc_library_service as poc_module
from main import app
from services.dependency_checker import check_python_code_dependencies
from services.poc_library_service import PocLibraryService


class TestPocLibraryService(PocLibraryService):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pocs_dir = self.base_dir / "pocs"
        self.db_path = self.pocs_dir / "poc_library.db"
        self.init_storage()
        self.init_database()


class DependencyCheckerTests(unittest.TestCase):
    def test_detects_missing_dependency_from_code(self):
        result = check_python_code_dependencies(
            "import json\nimport requests\nimport fake_missing_lib_xyz\n"
        )
        self.assertFalse(result["ok"])
        self.assertIn("fake_missing_lib_xyz", result["missing"])
        self.assertIn("requests", result["imports"])


class DependencyPrecheckIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._temp_dir.name)
        self.poc_service = TestPocLibraryService(self.base_dir)
        self._original_route_poc = routes_module.poc_library_service
        self._original_route_llm = routes_module.llm_service
        self._original_route_llm_generate = routes_module.llm_service.generate_initial_poc
        self._original_module_poc = poc_module.poc_library_service
        routes_module.poc_library_service = self.poc_service
        poc_module.poc_library_service = self.poc_service
        self.client = TestClient(app)

    def tearDown(self):
        routes_module.poc_library_service = self._original_route_poc
        routes_module.llm_service = self._original_route_llm
        routes_module.llm_service.generate_initial_poc = self._original_route_llm_generate
        poc_module.poc_library_service = self._original_module_poc
        self.client.close()
        self.poc_service = None
        gc.collect()
        for _ in range(5):
            try:
                self._temp_dir.cleanup()
                break
            except PermissionError:
                time.sleep(0.1)
        else:
            self.fail("临时测试目录清理失败，数据库文件仍被占用")

    def test_execute_poc_blocks_missing_dependency_before_import(self):
        poc_id = self.poc_service.save_poc(
            vuln_type="demo",
            vuln_name="缺依赖测试",
            vuln_info="demo",
            poc_code="import fake_missing_lib_xyz\n\ndef scan(url):\n    return {'vulnerable': False}\n",
            explanation="demo",
            verifiable=True,
        )

        result = self.poc_service.execute_poc(poc_id, "http://example.com")

        self.assertFalse(result["success"])
        self.assertIn("缺少依赖", result["error"])
        self.assertEqual(result["classification"]["failure_category"], "environment_error")
        self.assertEqual(result["classification"]["failure_code"], "missing_dependency")

    def test_generate_route_returns_dependency_check_summary(self):
        routes_module.llm_service.generate_initial_poc = AsyncMock(return_value={
            "verifiable": True,
            "vulnerability_name": "Demo Missing Dependency",
            "vulnerability_type": "demo",
            "original_vulnerability_info": "demo info",
            "execution_mode": "url_only",
            "verification_method": "direct",
            "input_schema": None,
            "poc_code": "import fake_missing_lib_xyz\n\ndef scan(url):\n    return {'vulnerable': False, 'reason': 'demo'}\n",
            "manual_steps": None,
            "explanation": "demo",
        })

        response = self.client.post(
            "/api/generate-poc",
            json={"vulnerability_info": "demo vulnerability"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('"dependency_check"', response.text)
        self.assertIn('"ok": false', response.text.lower())
        self.assertIn('fake_missing_lib_xyz', response.text)


if __name__ == "__main__":
    unittest.main()
