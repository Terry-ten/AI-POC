import gc
import tempfile
import time
import unittest
from pathlib import Path

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


class BatchReportExportTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._temp_dir.name)
        self.poc_service = TestPocLibraryService(self.base_dir)
        self.batch_service = TestBatchTaskService(self.base_dir)

        self.poc_id = self.poc_service.save_poc(
            vuln_type="ssrf",
            vuln_name="测试 SSRF",
            vuln_info="test vuln",
            poc_code="def scan(url):\n    return {'vulnerable': False, 'reason': 'ok', 'details': ''}\n",
            explanation="test",
            verifiable=True,
        )

        with self.batch_service.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO batch_tasks
                (mode, status, total_items, completed_items, success_items, failed_items, vulnerable_items, concurrency, config_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "multi_url_single_poc",
                    "completed",
                    2,
                    2,
                    1,
                    1,
                    0,
                    2,
                    '{"url_count": 2, "poc_count": 1}',
                ),
            )
            self.task_id = cursor.lastrowid
            cursor.executemany(
                """
                INSERT INTO batch_task_items
                (task_id, poc_id, target_url, engine_type, status, vulnerable, reason, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (self.task_id, self.poc_id, "http://127.0.0.1:8000", "poc", "success", 0, "未发现漏洞", None),
                    (self.task_id, self.poc_id, "http://not-exists.local", "poc", "failed", 0, "连接超时", "连接超时"),
                ],
            )

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

    def test_build_task_report_payload_contains_summary_and_items(self):
        payload = self.batch_service.build_task_report_payload(self.task_id)
        self.assertEqual(payload["summary"]["total_items"], 2)
        self.assertEqual(payload["summary"]["miss_items"], 1)
        self.assertEqual(payload["summary"]["exception_items"], 1)
        self.assertEqual(len(payload["items"]), 2)

    def test_export_json_report_contains_task_and_items(self):
        filename, content_type, content = self.batch_service.export_task_report(self.task_id, "json")
        text = content.decode("utf-8")
        self.assertTrue(filename.endswith(".json"))
        self.assertIn("application/json", content_type)
        self.assertIn('"summary"', text)
        self.assertIn('"items"', text)
        self.assertIn("http://127.0.0.1:8000", text)

    def test_export_html_and_txt_reports_contain_expected_labels(self):
        html_filename, html_type, html_content = self.batch_service.export_task_report(self.task_id, "html")
        txt_filename, txt_type, txt_content = self.batch_service.export_task_report(self.task_id, "txt")

        self.assertTrue(html_filename.endswith(".html"))
        self.assertIn("text/html", html_type)
        self.assertIn("批量检测报告", html_content.decode("utf-8"))

        self.assertTrue(txt_filename.endswith(".txt"))
        self.assertIn("text/plain", txt_type)
        self.assertIn("子任务结果", txt_content.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
