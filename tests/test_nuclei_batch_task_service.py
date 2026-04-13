import gc
import tempfile
import time
import unittest
from pathlib import Path

import services.batch_task_service as batch_module
from services.batch_task_service import BatchTaskService
from services.poc_library_service import PocLibraryService


class FakeNucleiService:
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir

    def scan_single(self, target_url: str, template_path: str, timeout: int = 60):
        return {
            "success": True,
            "target_url": target_url,
            "findings": [
                {
                    "template_id": "fake-template",
                    "template_name": "Fake Template",
                    "severity": "medium",
                    "matched_at": f"{target_url}/hit",
                }
            ],
            "total_findings": 1,
            "vulnerable": True,
            "errors": None,
        }


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


class NucleiBatchTaskServiceTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._temp_dir.name)
        (self.base_dir / "pocs" / "nuclei").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "pocs" / "nuclei" / "test.yaml").write_text("id: fake-template\n", encoding="utf-8")

        self.poc_service = TestPocLibraryService(self.base_dir)
        self.batch_service = TestBatchTaskService(self.base_dir)

        self._original_poc_service = batch_module.poc_library_service
        self._original_nuclei_service = batch_module.nuclei_service
        batch_module.poc_library_service = self.poc_service
        batch_module.nuclei_service = FakeNucleiService(self.base_dir / "pocs" / "nuclei")

    def tearDown(self):
        batch_module.poc_library_service = self._original_poc_service
        batch_module.nuclei_service = self._original_nuclei_service
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

    def test_create_nuclei_task_creates_nuclei_items(self):
        task = self.batch_service.create_nuclei_task(
            target_urls=["http://example.com"],
            template_paths=["test.yaml"],
            concurrency=1,
        )

        timeout_at = time.time() + 5
        while time.time() < timeout_at:
            current = self.batch_service.get_task(task["id"])
            if current["status"] == "completed":
                break
            time.sleep(0.1)
        else:
            self.fail("Nuclei 批量任务未在预期时间内完成")

        task = self.batch_service.get_task(task["id"])
        items = self.batch_service.get_task_items(task["id"], limit=10)["items"]

        self.assertEqual(task["task_type"], "nuclei_scan")
        self.assertEqual(task["mode"], "single_url_single_poc")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["engine_type"], "nuclei")
        self.assertEqual(items[0]["template_path"], "test.yaml")
        self.assertTrue(items[0]["vulnerable"])
        self.assertEqual(items[0]["status"], "success")

    def test_build_task_report_payload_marks_nuclei_unit(self):
        task = self.batch_service.create_nuclei_task(
            target_urls=["http://example.com"],
            template_paths=["test.yaml"],
            concurrency=1,
        )

        timeout_at = time.time() + 5
        while time.time() < timeout_at:
            current = self.batch_service.get_task(task["id"])
            if current["status"] == "completed":
                break
            time.sleep(0.1)

        payload = self.batch_service.build_task_report_payload(task["id"])
        self.assertEqual(payload["summary"]["task_type"], "nuclei_scan")
        self.assertEqual(payload["summary"]["unit_label"], "模板")
        self.assertEqual(payload["summary"]["unit_count"], 1)
        self.assertEqual(payload["summary"]["hit_items"], 1)

    def test_export_nuclei_report_uses_template_label(self):
        task = self.batch_service.create_nuclei_task(
            target_urls=["http://example.com"],
            template_paths=["test.yaml"],
            concurrency=1,
        )

        timeout_at = time.time() + 5
        while time.time() < timeout_at:
            current = self.batch_service.get_task(task["id"])
            if current["status"] == "completed":
                break
            time.sleep(0.1)

        _, _, text_report = self.batch_service.export_task_report(task["id"], "txt")
        _, _, html_report = self.batch_service.export_task_report(task["id"], "html")
        self.assertIn("模板 数量: 1", text_report.decode("utf-8"))
        self.assertIn("模板: test.yaml", text_report.decode("utf-8"))
        self.assertIn("模板 数量", html_report.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
