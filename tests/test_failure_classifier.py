import gc
import tempfile
import time
import unittest
from pathlib import Path

from services.batch_task_service import BatchTaskService
from services.failure_classifier import classify_execution_outcome
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


class FailureClassifierTests(unittest.TestCase):
    def test_classify_network_timeout(self):
        classification = classify_execution_outcome({
            "success": False,
            "error": "HTTPConnectionPool(host='demo.local', port=80): Read timed out.",
            "result": {
                "vulnerable": False,
                "reason": "目标不可达或请求超时",
                "details": "Read timed out",
            },
        })
        self.assertEqual(classification["failure_category"], "network_error")
        self.assertEqual(classification["failure_code"], "read_timeout")
        self.assertTrue(classification["retryable"])

    def test_classify_syntax_error(self):
        classification = classify_execution_outcome({
            "success": False,
            "error": "SyntaxError: unexpected character after line continuation character",
        })
        self.assertEqual(classification["failure_category"], "code_error")
        self.assertEqual(classification["failure_code"], "syntax_error")
        self.assertFalse(classification["retryable"])


class FailureClassificationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._temp_dir.name)
        self.poc_service = TestPocLibraryService(self.base_dir)
        self.batch_service = TestBatchTaskService(self.base_dir)

    def tearDown(self):
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

    def test_execute_poc_returns_structured_not_vulnerable_classification(self):
        poc_id = self.poc_service.save_poc(
            vuln_type="file-read",
            vuln_name="测试未命中",
            vuln_info="demo",
            poc_code="def scan(url):\n    return {'vulnerable': False, 'reason': '未发现漏洞特征', 'details': {'url': url}}\n",
            explanation="demo",
            verifiable=True,
        )

        result = self.poc_service.execute_poc(poc_id, "http://example.com")

        self.assertTrue(result["success"])
        self.assertEqual(result["classification"]["failure_category"], "not_vulnerable")
        self.assertEqual(result["classification"]["failure_code"], "no_evidence_found")
        self.assertEqual(result["classification"]["failure_stage"], "result_judgement")

    def test_batch_item_persists_structured_failure_fields(self):
        with self.batch_service.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO batch_tasks (task_type, mode, status, total_items, concurrency, config_json)
                VALUES ('poc_batch', 'single_url_single_poc', 'running', 1, 1, '{}')
                """
            )
            task_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO batch_task_items (task_id, poc_id, target_url, engine_type, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, 0, "http://demo.local", "poc", "running"),
            )
            item_id = cursor.lastrowid

        self.batch_service._store_item_result(item_id, {
            "success": False,
            "error": "HTTPConnectionPool(host='demo.local', port=80): Read timed out.",
            "result": {
                "vulnerable": False,
                "reason": "目标不可达或请求超时",
                "details": "Read timed out",
            },
        })

        items = self.batch_service.get_task_items(task_id, limit=10)["items"]
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["failure_category"], "network_error")
        self.assertEqual(item["failure_code"], "read_timeout")
        self.assertEqual(item["failure_stage"], "request_send")
        self.assertTrue(item["retryable"])


if __name__ == "__main__":
    unittest.main()
