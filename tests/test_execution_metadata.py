import sqlite3
import tempfile
import unittest
import gc
import time
from pathlib import Path

from services.poc_library_service import PocLibraryService


class TestPocLibraryService(PocLibraryService):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pocs_dir = self.base_dir / "pocs"
        self.db_path = self.pocs_dir / "poc_library.db"
        self.init_storage()
        self.init_database()


class ExecutionMetadataTests(unittest.TestCase):
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

    def test_verifiable_record_defaults_to_url_only_and_direct(self):
        with sqlite3.connect(self.service.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO poc_records
                (vuln_type, vuln_name, vuln_description, poc_type, poc_file_path, verifiable)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "sqli",
                    "Legacy SQLi",
                    "legacy record",
                    "python",
                    str(self.service.pocs_dir / "python" / "legacy.py"),
                    1,
                ),
            )
            poc_id = cursor.lastrowid
            conn.commit()

        record = self.service.get_poc_by_id(poc_id)
        self.assertEqual(record["execution_mode"], "url_only")
        self.assertEqual(record["verification_method"], "direct")
        self.assertIsNone(record["input_schema"])

    def test_manual_record_defaults_to_manual_guide_and_manual(self):
        with sqlite3.connect(self.service.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO poc_records
                (vuln_type, vuln_name, vuln_description, poc_type, poc_file_path, verifiable)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "rce",
                    "Legacy Manual Guide",
                    "legacy manual record",
                    "manual",
                    str(self.service.pocs_dir / "metadata" / "legacy.json"),
                    0,
                ),
            )
            poc_id = cursor.lastrowid
            conn.commit()

        record = self.service.get_poc_by_id(poc_id)
        self.assertEqual(record["execution_mode"], "manual_guide")
        self.assertEqual(record["verification_method"], "manual")
        self.assertIsNone(record["input_schema"])

    def test_save_poc_persists_execution_metadata(self):
        poc_id = self.service.save_poc(
            vuln_type="ssrf",
            vuln_name="Test SSRF",
            vuln_info="test vulnerability info",
            poc_code="def scan(url):\n    return {'vulnerable': False, 'reason': 'ok', 'details': ''}\n",
            explanation="test explanation",
            poc_type="python",
            verifiable=True,
            execution_mode="url_with_params",
            verification_method="direct",
            input_schema=[
                {
                    "name": "cookie",
                    "type": "textarea",
                    "required": True,
                    "label": "Cookie",
                }
            ],
        )

        record = self.service.get_poc_by_id(poc_id)
        self.assertEqual(record["execution_mode"], "url_with_params")
        self.assertEqual(record["verification_method"], "direct")
        self.assertEqual(
            record["input_schema"],
            [
                {
                    "name": "cookie",
                    "type": "textarea",
                    "required": True,
                    "label": "Cookie",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
