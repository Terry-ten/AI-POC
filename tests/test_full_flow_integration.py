import gc
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import api.routes as routes_module
import services.batch_task_service as batch_module
import services.poc_library_service as poc_module
from main import app
from services.asset_source_service import AssetSourceService
from services.batch_task_service import BatchTaskService
from services.oob_service import OOBService
from services.poc_library_service import PocLibraryService


class TestPocLibraryService(PocLibraryService):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pocs_dir = self.base_dir / "pocs"
        self.db_path = self.pocs_dir / "poc_library.db"
        self.init_storage()
        self.init_database()


class TestBatchTaskService(BatchTaskService):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.db_path = self.base_dir / "pocs" / "poc_library.db"
        self.batch_results_dir = self.base_dir / "pocs" / "batch_results"
        self.batch_results_dir.mkdir(parents=True, exist_ok=True)
        self._cancel_events = {}
        self._worker_threads = {}
        import threading
        self._lock = threading.Lock()
        self.init_database()


class FakeOOBClient:
    def build_probe(self, protocol="http", length=10, value=""):
        return {"url": "http://oob.example.test", "flag": "flag123"}

    def verify(self, flag, protocol="http"):
        return {"matched": True, "events": [{"flag": flag}], "error": None}


class FakeNucleiService:
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir

    def get_templates_by_folder(self, folder: str = "", page: int = 1, page_size: int = 100, keyword: str = ""):
        return ([{"relative_path": "demo/test.yaml"}], 1)

    def scan_single(self, target_url: str, template_path: str, timeout: int = 60):
        return {
            "success": True,
            "target_url": target_url,
            "findings": [{"template_id": "demo/test"}],
            "total_findings": 1,
            "vulnerable": True,
            "errors": None,
        }


class FullFlowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._temp_dir.name)

        self.poc_service = TestPocLibraryService(self.base_dir)
        self.batch_service = TestBatchTaskService(self.base_dir)
        self.oob_service = OOBService(
            config_file=self.base_dir / "pocs" / "oob_config.json",
            provider_factories={
                "ceye": lambda **kwargs: FakeOOBClient(),
                "interactsh": lambda **kwargs: FakeOOBClient(),
            },
        )
        (self.base_dir / "pocs" / "nuclei" / "demo").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "pocs" / "nuclei" / "demo" / "test.yaml").write_text("id: demo\n", encoding="utf-8")
        self.nuclei_service = FakeNucleiService(self.base_dir / "pocs" / "nuclei")
        self.asset_service = AssetSourceService(
            config_file=self.base_dir / "pocs" / "asset_source_config.json",
            provider_factories={
                "fofa": lambda: type("Client", (), {"search": lambda self, q, pages: ["http://asset-one.test", "http://asset-two.test"]})(),
            },
        )

        self._original_services = {
            "route_poc": routes_module.poc_library_service,
            "route_batch": routes_module.batch_task_service,
            "route_oob": routes_module.oob_service,
            "route_nuclei": routes_module.nuclei_service,
            "route_asset": routes_module.asset_source_service,
            "route_llm": routes_module.llm_service,
            "route_llm_generate": routes_module.llm_service.generate_initial_poc,
            "module_poc": poc_module.poc_library_service,
            "module_batch_poc": batch_module.poc_library_service,
            "module_batch_nuclei": batch_module.nuclei_service,
        }

        routes_module.poc_library_service = self.poc_service
        routes_module.batch_task_service = self.batch_service
        routes_module.oob_service = self.oob_service
        routes_module.nuclei_service = self.nuclei_service
        routes_module.asset_source_service = self.asset_service
        poc_module.poc_library_service = self.poc_service
        batch_module.poc_library_service = self.poc_service
        batch_module.nuclei_service = self.nuclei_service

        self.client = TestClient(app)

    def tearDown(self):
        routes_module.poc_library_service = self._original_services["route_poc"]
        routes_module.batch_task_service = self._original_services["route_batch"]
        routes_module.oob_service = self._original_services["route_oob"]
        routes_module.nuclei_service = self._original_services["route_nuclei"]
        routes_module.asset_source_service = self._original_services["route_asset"]
        routes_module.llm_service = self._original_services["route_llm"]
        routes_module.llm_service.generate_initial_poc = self._original_services["route_llm_generate"]
        poc_module.poc_library_service = self._original_services["module_poc"]
        batch_module.poc_library_service = self._original_services["module_batch_poc"]
        batch_module.nuclei_service = self._original_services["module_batch_nuclei"]
        self.client.close()
        self.batch_service = None
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

    def test_generate_search_and_execute_with_runtime_params(self):
        mocked_llm = AsyncMock(return_value={
            "verifiable": True,
            "vulnerability_name": "Demo Param Vulnerability",
            "vulnerability_type": "auth-bypass",
            "original_vulnerability_info": "demo info",
            "execution_mode": "url_with_params",
            "verification_method": "direct",
            "input_schema": [
                {"name": "cookie", "type": "textarea", "required": True, "label": "Cookie"}
            ],
            "poc_code": """
def scan(url, runtime_params):
    cookie = runtime_params.get("cookie", "")
    return {"vulnerable": bool(cookie), "reason": cookie or "missing", "details": {"url": url}}
""".strip(),
            "manual_steps": None,
            "explanation": "demo",
        })

        routes_module.llm_service.generate_initial_poc = mocked_llm

        response = self.client.post(
            "/api/generate-poc",
            json={"vulnerability_info": "demo vulnerability"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('"type": "result"', response.text)

        search_resp = self.client.get("/api/pocs/search?limit=10")
        self.assertEqual(search_resp.status_code, 200)
        search_data = search_resp.json()
        self.assertTrue(search_data["success"])
        poc = search_data["pocs"][0]
        self.assertEqual(poc["execution_mode"], "url_with_params")
        self.assertEqual(poc["verification_method"], "direct")

        execute_resp = self.client.post(
            f"/api/pocs/{poc['id']}/execute",
            json={
                "target_url": "http://example.com",
                "runtime_params": {"cookie": "PHPSESSID=test"},
            },
        )
        self.assertEqual(execute_resp.status_code, 200)
        execute_data = execute_resp.json()
        self.assertTrue(execute_data["success"])
        self.assertTrue(execute_data["result"]["vulnerable"])
        self.assertEqual(execute_data["result"]["reason"], "PHPSESSID=test")

    def test_batch_task_records_and_export_flow(self):
        poc_id = self.poc_service.save_poc(
            vuln_type="ssrf",
            vuln_name="Batch URL Only",
            vuln_info="batch info",
            poc_code="def scan(url):\n    return {'vulnerable': False, 'reason': 'ok', 'details': url}\n",
            explanation="test",
            verifiable=True,
            execution_mode="url_only",
            verification_method="direct",
        )

        create_resp = self.client.post(
            "/api/batch-tasks",
            json={
                "target_urls": ["http://example.com", "http://example.org"],
                "poc_ids": [poc_id],
                "concurrency": 1,
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        task_id = create_resp.json()["task"]["id"]

        deadline = time.time() + 5
        task = None
        while time.time() < deadline:
            task_resp = self.client.get(f"/api/batch-tasks/{task_id}")
            task = task_resp.json()["task"]
            if task["status"] == "completed":
                break
            time.sleep(0.1)

        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["total_items"], 2)

        items_resp = self.client.get(f"/api/batch-tasks/{task_id}/items?limit=20")
        self.assertEqual(items_resp.status_code, 200)
        items = items_resp.json()["items"]
        self.assertEqual(len(items), 2)
        self.assertTrue(all(item["status"] == "success" for item in items))

        export_resp = self.client.get(f"/api/batch-tasks/{task_id}/export?format=json")
        self.assertEqual(export_resp.status_code, 200)
        payload = json.loads(export_resp.text)
        self.assertEqual(payload["task"]["id"], task_id)
        self.assertEqual(payload["summary"]["total_items"], 2)

    def test_config_and_import_endpoints(self):
        oob_update = self.client.post(
            "/api/config/oob",
            json={
                "enabled": True,
                "provider": "ceye",
                "ceye_token": "abcdef123456",
                "ceye_base_url": "http://api.ceye.io/v1",
                "poll_interval": 1.0,
                "max_polls": 2,
            },
        )
        self.assertEqual(oob_update.status_code, 200)
        self.assertTrue(oob_update.json()["success"])

        oob_get = self.client.get("/api/config/oob")
        self.assertEqual(oob_get.status_code, 200)
        self.assertEqual(oob_get.json()["config"]["provider"], "ceye")

        asset_update = self.client.post(
            "/api/config/asset-sources",
            json={"provider": "fofa", "email": "demo@example.com", "token": "abc123456"},
        )
        self.assertEqual(asset_update.status_code, 200)
        self.assertTrue(asset_update.json()["success"])

        import_resp = self.client.post(
            "/api/asset-sources/import",
            json={"provider": "fofa", "query": 'body="ecshop"', "pages": 1},
        )
        self.assertEqual(import_resp.status_code, 200)
        import_data = import_resp.json()
        self.assertTrue(import_data["success"])
        self.assertEqual(import_data["total"], 2)
        self.assertIn("http://asset-one.test", import_data["targets"])

    def test_nuclei_task_flow(self):
        create_resp = self.client.post(
            "/api/nuclei/tasks",
            json={
                "target_urls": ["http://example.com"],
                "template_paths": ["demo/test.yaml"],
                "concurrency": 1,
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        task_id = create_resp.json()["task"]["id"]

        deadline = time.time() + 5
        task = None
        while time.time() < deadline:
            task_resp = self.client.get(f"/api/batch-tasks/{task_id}")
            task = task_resp.json()["task"]
            if task["status"] == "completed":
                break
            time.sleep(0.1)

        self.assertIsNotNone(task)
        self.assertEqual(task["task_type"], "nuclei_scan")

        items_resp = self.client.get(f"/api/batch-tasks/{task_id}/items?limit=20")
        self.assertEqual(items_resp.status_code, 200)
        items = items_resp.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["engine_type"], "nuclei")
        self.assertEqual(items[0]["template_path"], "demo/test.yaml")
        self.assertTrue(items[0]["vulnerable"])


if __name__ == "__main__":
    unittest.main()
