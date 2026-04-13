import gc
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from main import app
import services.batch_task_service as batch_task_module
from services.batch_task_service import BatchTaskService
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


class ApiRouteRegressionTests(unittest.TestCase):
    def test_poc_statistics_and_vuln_types_routes_are_not_captured_by_id_route(self):
        client = TestClient(app)

        stats_resp = client.get("/api/pocs/statistics")
        types_resp = client.get("/api/pocs/vuln-types")

        self.assertEqual(stats_resp.status_code, 200)
        self.assertTrue(stats_resp.json().get("success"))
        self.assertEqual(types_resp.status_code, 200)
        self.assertTrue(types_resp.json().get("success"))


class BatchCancelRegressionTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._temp_dir.name)
        self.poc_service = TestPocLibraryService(self.base_dir)
        self.batch_service = TestBatchTaskService(self.base_dir)
        self._original_poc_library_service = batch_task_module.poc_library_service
        batch_task_module.poc_library_service = self.poc_service

        self.poc_id = self.poc_service.save_poc(
            vuln_type="demo",
            vuln_name="Cancel Regression",
            vuln_info="demo",
            poc_code=(
                "import time\n"
                "def scan(url):\n"
                "    time.sleep(0.5)\n"
                "    return {'vulnerable': False, 'reason': 'ok', 'details': ''}\n"
            ),
            explanation="demo",
            verifiable=True,
        )

    def tearDown(self):
        batch_task_module.poc_library_service = self._original_poc_library_service
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

    def test_cancelled_task_does_not_leave_running_items(self):
        task = self.batch_service.create_task(
            target_urls=["http://example.com", "http://example.org"],
            poc_ids=[self.poc_id],
            concurrency=1,
        )
        task_id = task["id"]

        self.assertTrue(self.batch_service.cancel_task(task_id))

        deadline = time.time() + 5
        while time.time() < deadline:
            current_task = self.batch_service.get_task(task_id)
            items = self.batch_service.get_task_items(task_id, limit=10)["items"]
            item_statuses = {item["status"] for item in items}
            if current_task["status"] == "cancelled" and "running" not in item_statuses:
                break
            time.sleep(0.1)

        current_task = self.batch_service.get_task(task_id)
        items = self.batch_service.get_task_items(task_id, limit=10)["items"]
        item_statuses = {item["status"] for item in items}

        self.assertEqual(current_task["status"], "cancelled")
        self.assertNotIn("running", item_statuses)
        self.assertIn("cancelled", item_statuses)


if __name__ == "__main__":
    unittest.main()
