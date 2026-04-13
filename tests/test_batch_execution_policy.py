import gc
import tempfile
import time
import unittest
from pathlib import Path

import services.batch_task_service as batch_module
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


class BatchExecutionPolicyTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._temp_dir.name)
        self.poc_service = TestPocLibraryService(self.base_dir)
        self.batch_service = TestBatchTaskService(self.base_dir)
        self._original_poc_service = batch_module.poc_library_service
        batch_module.poc_library_service = self.poc_service

    def tearDown(self):
        batch_module.poc_library_service = self._original_poc_service
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

    def test_create_task_accepts_url_only_poc(self):
        poc_id = self.poc_service.save_poc(
            vuln_type="ssrf",
            vuln_name="URL Only POC",
            vuln_info="test url only",
            poc_code="def scan(url):\n    return {'vulnerable': False, 'reason': 'ok', 'details': ''}\n",
            explanation="test",
            verifiable=True,
            execution_mode="url_only",
            verification_method="direct",
        )

        task = self.batch_service.create_task(
            target_urls=["http://example.com"],
            poc_ids=[poc_id],
            concurrency=1,
        )

        self.assertEqual(task["mode"], "single_url_single_poc")
        self.assertEqual(task["total_items"], 1)

    def test_create_task_rejects_url_with_params_poc(self):
        poc_id = self.poc_service.save_poc(
            vuln_type="auth-bypass",
            vuln_name="Param POC",
            vuln_info="test params",
            poc_code="def scan(url, runtime_params):\n    return {'vulnerable': False, 'reason': 'ok', 'details': runtime_params}\n",
            explanation="test",
            verifiable=True,
            execution_mode="url_with_params",
            verification_method="direct",
            input_schema=[{"name": "cookie", "type": "textarea", "required": True}],
        )

        with self.assertRaisesRegex(ValueError, "仅支持 url_only 类型"):
            self.batch_service.create_task(
                target_urls=["http://example.com"],
                poc_ids=[poc_id],
                concurrency=1,
            )


if __name__ == "__main__":
    unittest.main()
