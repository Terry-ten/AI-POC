"""
批量任务服务

负责：
1. 批量任务创建与拆分
2. 后台任务执行
3. 任务状态与结果查询
4. 批量任务取消
"""

import json
import logging
import sqlite3
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from html import escape
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from services.nuclei_service import nuclei_service
from services.failure_classifier import classify_execution_outcome
from services.poc_library_service import poc_library_service

logger = logging.getLogger(__name__)


class BatchTaskService:
    """批量任务编排服务"""

    MAX_URLS = 200
    MAX_POCS = 50
    MAX_TASK_ITEMS = 2000
    DEFAULT_CONCURRENCY = 3
    MAX_CONCURRENCY = 5

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.db_path = self.base_dir / "pocs" / "poc_library.db"
        self.batch_results_dir = self.base_dir / "pocs" / "batch_results"
        self.batch_results_dir.mkdir(parents=True, exist_ok=True)
        self._cancel_events: Dict[int, threading.Event] = {}
        self._worker_threads: Dict[int, threading.Thread] = {}
        self._lock = threading.Lock()
        self.init_database()

    @contextmanager
    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_database(self):
        """初始化批量任务相关表"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL DEFAULT 'poc_batch',
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    total_items INTEGER NOT NULL DEFAULT 0,
                    completed_items INTEGER NOT NULL DEFAULT 0,
                    success_items INTEGER NOT NULL DEFAULT 0,
                    failed_items INTEGER NOT NULL DEFAULT 0,
                    vulnerable_items INTEGER NOT NULL DEFAULT 0,
                    concurrency INTEGER NOT NULL DEFAULT 3,
                    config_json TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_task_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    poc_id INTEGER NOT NULL,
                    target_url TEXT NOT NULL,
                    engine_type TEXT NOT NULL DEFAULT 'poc',
                    template_path TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result_json TEXT,
                    error TEXT,
                    failure_category TEXT,
                    failure_code TEXT,
                    failure_stage TEXT,
                    retryable INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    FOREIGN KEY(task_id) REFERENCES batch_tasks(id)
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_tasks_status ON batch_tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_task_items_task_id ON batch_task_items(task_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_task_items_status ON batch_task_items(status)")
            self._ensure_batch_task_item_columns(cursor)
            self._backfill_batch_task_item_summaries(cursor)

    def create_task(self, target_urls: List[str], poc_ids: List[int], concurrency: Optional[int] = None) -> Dict:
        """创建批量任务并启动后台执行"""
        urls = self._normalize_urls(target_urls)
        unique_poc_ids = self._normalize_poc_ids(poc_ids)
        selected_pocs = self._validate_pocs(unique_poc_ids)

        if not urls:
            raise ValueError("至少需要一个目标URL")
        if not selected_pocs:
            raise ValueError("至少需要一个可执行POC")

        if len(urls) > self.MAX_URLS:
            raise ValueError(f"URL数量超出限制，最多允许 {self.MAX_URLS} 个")
        if len(selected_pocs) > self.MAX_POCS:
            raise ValueError(f"POC数量超出限制，最多允许 {self.MAX_POCS} 个")

        total_items = len(urls) * len(selected_pocs)
        if total_items > self.MAX_TASK_ITEMS:
            raise ValueError(f"任务总数超出限制，最多允许 {self.MAX_TASK_ITEMS} 个子任务")

        task_mode = self._infer_mode(len(urls), len(selected_pocs))
        worker_count = max(1, min(int(concurrency or self.DEFAULT_CONCURRENCY), self.MAX_CONCURRENCY))

        task_config = {
            "target_urls": urls,
            "poc_ids": [p["id"] for p in selected_pocs],
            "poc_names": {str(p["id"]): p.get("vuln_name") for p in selected_pocs},
            "url_count": len(urls),
            "poc_count": len(selected_pocs),
        }

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO batch_tasks (task_type, mode, status, total_items, concurrency, config_json)
                VALUES ('poc_batch', ?, 'pending', ?, ?, ?)
                """,
                (task_mode, total_items, worker_count, json.dumps(task_config, ensure_ascii=False)),
            )
            task_id = cursor.lastrowid

            item_rows = []
            for url in urls:
                for poc in selected_pocs:
                    item_rows.append((task_id, poc["id"], url, "poc", "pending"))

            cursor.executemany(
                """
                INSERT INTO batch_task_items (task_id, poc_id, target_url, engine_type, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                item_rows,
            )

        self.start_task(task_id)
        return self.get_task(task_id)

    def create_nuclei_task(
        self,
        target_urls: List[str],
        template_paths: List[str],
        concurrency: Optional[int] = None,
    ) -> Dict:
        """创建 Nuclei 批量任务并启动后台执行"""
        urls = self._normalize_urls(target_urls)
        templates = self._normalize_template_paths(template_paths)

        if not urls:
            raise ValueError("至少需要一个目标URL")
        if not templates:
            raise ValueError("至少需要一个有效的 Nuclei 模板")

        if len(urls) > self.MAX_URLS:
            raise ValueError(f"URL数量超出限制，最多允许 {self.MAX_URLS} 个")
        if len(templates) > self.MAX_POCS:
            raise ValueError(f"模板数量超出限制，最多允许 {self.MAX_POCS} 个")

        total_items = len(urls) * len(templates)
        if total_items > self.MAX_TASK_ITEMS:
            raise ValueError(f"任务总数超出限制，最多允许 {self.MAX_TASK_ITEMS} 个子任务")

        task_mode = self._infer_mode(len(urls), len(templates))
        worker_count = max(1, min(int(concurrency or self.DEFAULT_CONCURRENCY), self.MAX_CONCURRENCY))
        task_config = {
            "target_urls": urls,
            "template_paths": templates,
            "url_count": len(urls),
            "template_count": len(templates),
            "poc_count": len(templates),
        }

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO batch_tasks (task_type, mode, status, total_items, concurrency, config_json)
                VALUES ('nuclei_scan', ?, 'pending', ?, ?, ?)
                """,
                (task_mode, total_items, worker_count, json.dumps(task_config, ensure_ascii=False)),
            )
            task_id = cursor.lastrowid

            item_rows = []
            for url in urls:
                for template_path in templates:
                    item_rows.append((task_id, 0, url, "nuclei", template_path, "pending"))

            cursor.executemany(
                """
                INSERT INTO batch_task_items (task_id, poc_id, target_url, engine_type, template_path, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                item_rows,
            )

        self.start_task(task_id)
        return self.get_task(task_id)

    def start_task(self, task_id: int):
        """启动后台任务线程"""
        with self._lock:
            thread = self._worker_threads.get(task_id)
            if thread and thread.is_alive():
                return

            cancel_event = self._cancel_events.get(task_id) or threading.Event()
            self._cancel_events[task_id] = cancel_event

            worker = threading.Thread(
                target=self._run_task,
                args=(task_id, cancel_event),
                daemon=True,
                name=f"batch-task-{task_id}",
            )
            self._worker_threads[task_id] = worker
            worker.start()

    def list_tasks(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        result_filter: Optional[str] = None,
        keyword: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Dict:
        sort_field = {
            "created_at": "created_at",
            "finished_at": "finished_at",
            "vulnerable_items": "vulnerable_items",
            "failed_items": "failed_items",
        }.get(sort_by, "created_at")
        sort_direction = "ASC" if str(sort_order).lower() == "asc" else "DESC"

        query = """
            SELECT *
            FROM batch_tasks
            WHERE 1=1
        """
        params: List = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if result_filter == "hit":
            query += " AND vulnerable_items > 0"
        elif result_filter == "failed":
            query += " AND failed_items > 0"
        elif result_filter == "clean":
            query += " AND status = 'completed' AND vulnerable_items = 0 AND failed_items = 0"

        if keyword:
            pattern = f"%{keyword.strip()}%"
            query += " AND (CAST(id AS TEXT) LIKE ? OR config_json LIKE ?)"
            params.extend([pattern, pattern])

        count_query = f"SELECT COUNT(*) FROM ({query})"
        query += f" ORDER BY {sort_field} {sort_direction}, id DESC LIMIT ? OFFSET ?"
        params_with_page = params + [limit, offset]

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            cursor.execute(query, params_with_page)
            rows = [self._serialize_task_row(dict(row)) for row in cursor.fetchall()]
        return {"total": total, "tasks": rows}

    def get_task(self, task_id: int) -> Optional[Dict]:
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM batch_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._serialize_task_row(dict(row))

    def get_task_items(
        self,
        task_id: int,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Dict:
        query = """
            SELECT i.*, p.vuln_name, p.vuln_type, p.poc_type
            FROM batch_task_items i
            LEFT JOIN poc_records p ON p.id = i.poc_id
            WHERE i.task_id = ?
        """
        params: List = [task_id]

        if status:
            query += " AND i.status = ?"
            params.append(status)

        if keyword:
            query += " AND (i.target_url LIKE ? OR p.vuln_name LIKE ? OR p.vuln_type LIKE ?)"
            pattern = f"%{keyword}%"
            params.extend([pattern, pattern, pattern])

        count_params = list(params)
        count_query = f"SELECT COUNT(*) FROM ({query})"
        query += " ORDER BY i.id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(count_query, count_params)
            total = cursor.fetchone()[0]
            cursor.execute(query, params)
            rows = [self._serialize_item_row(dict(row)) for row in cursor.fetchall()]

        return {"total": total, "items": rows}

    def get_task_item_detail(self, task_id: int, item_id: int) -> Optional[Dict]:
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT i.*, p.vuln_name, p.vuln_type, p.poc_type
                FROM batch_task_items i
                LEFT JOIN poc_records p ON p.id = i.poc_id
                WHERE i.task_id = ? AND i.id = ?
                """,
                (task_id, item_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            item = self._serialize_item_row(dict(row))
            detail_file = item.get("detail_file")
            if detail_file:
                detail_path = Path(detail_file)
                if detail_path.exists():
                    try:
                        with open(detail_path, "r", encoding="utf-8") as f:
                            item["detail"] = json.load(f)
                    except (OSError, json.JSONDecodeError) as exc:
                        logger.warning(f"读取批量任务详情文件失败: item={item_id}, error={exc}")
                        item["detail"] = {"success": False, "error": f"读取详情文件失败: {exc}"}
                else:
                    item["detail"] = {"success": False, "error": f"详情文件不存在: {detail_file}"}
            elif item.get("result_json") is not None:
                item["detail"] = item["result_json"]
            else:
                return None

            return item

    def cancel_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False

        with self._lock:
            event = self._cancel_events.get(task_id) or threading.Event()
            event.set()
            self._cancel_events[task_id] = event

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE batch_tasks
                SET status = 'cancelled', finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP)
                WHERE id = ? AND status IN ('pending', 'running')
                """,
                (task_id,),
            )
            cursor.execute(
                """
                UPDATE batch_task_items
                SET status = 'cancelled',
                    reason = COALESCE(reason, '任务已取消'),
                    finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP)
                WHERE task_id = ? AND status IN ('pending', 'running')
                """,
                (task_id,),
            )
        self._refresh_task_stats(task_id)
        return True

    def _run_task(self, task_id: int, cancel_event: threading.Event):
        try:
            task = self.get_task(task_id)
            if not task:
                return

            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE batch_tasks
                    SET status = 'running', started_at = COALESCE(started_at, CURRENT_TIMESTAMP)
                    WHERE id = ? AND status IN ('pending', 'running')
                    """,
                    (task_id,),
                )

            items = self.get_task_items(task_id, limit=self.MAX_TASK_ITEMS)["items"]
            pending_items = [item for item in items if item["status"] == "pending"]
            concurrency = task.get("concurrency") or self.DEFAULT_CONCURRENCY

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = {}
                item_iter = iter(pending_items)
                cancellation_requested = False

                while True:
                    if cancel_event.is_set():
                        cancellation_requested = True
                        break

                    while len(futures) < concurrency:
                        try:
                            item = next(item_iter)
                        except StopIteration:
                            break

                        self._mark_item_running(item["id"])
                        future = executor.submit(self._execute_task_item, item)
                        futures[future] = item["id"]

                    if not futures:
                        break

                    done, _ = wait(list(futures.keys()), return_when=FIRST_COMPLETED, timeout=0.5)
                    for future in done:
                        item_id = futures.pop(future)
                        try:
                            outcome = future.result()
                            self._store_item_result(item_id, outcome)
                        except Exception as e:
                            logger.error(f"批量子任务执行失败: task={task_id}, item={item_id}, error={e}")
                            self._store_item_result(item_id, {
                                "success": False,
                                "error": str(e),
                                "target_url": None,
                                "result": {
                                    "vulnerable": False,
                                    "reason": "批量任务执行异常",
                                    "details": str(e)
                                }
                            })
                        self._refresh_task_stats(task_id)

                if cancellation_requested and futures:
                    for future, item_id in list(futures.items()):
                        try:
                            outcome = future.result()
                        except Exception as e:
                            logger.warning(f"取消中的子任务收尾失败: task={task_id}, item={item_id}, error={e}")
                            outcome = {
                                "success": False,
                                "error": str(e),
                                "result": {
                                    "vulnerable": False,
                                    "reason": "任务已取消",
                                    "details": str(e),
                                },
                            }
                        self._store_item_cancelled(item_id, outcome)
                    futures.clear()
                    self._refresh_task_stats(task_id)

            self._finalize_task(task_id, cancel_event.is_set())
        finally:
            with self._lock:
                self._worker_threads.pop(task_id, None)
                self._cancel_events.pop(task_id, None)

    def _execute_task_item(self, item: Dict) -> Dict:
        item_id = item["id"]
        target_url = item["target_url"]
        engine_type = item.get("engine_type") or "poc"

        if engine_type == "nuclei":
            template_path = item.get("template_path")
            logger.info(f"执行 Nuclei 批量子任务: item={item_id}, template={template_path}, url={target_url}")
            return self._execute_nuclei_task_item(target_url, template_path)

        poc_id = item["poc_id"]
        logger.info(f"执行批量子任务: item={item_id}, poc={poc_id}, url={target_url}")
        return poc_library_service.execute_poc(poc_id, target_url)

    def _execute_nuclei_task_item(self, target_url: str, template_path: str) -> Dict:
        outcome = nuclei_service.scan_single(target_url, template_path, timeout=60)
        if not outcome.get("success"):
            return {
                "success": False,
                "error": outcome.get("error") or "Nuclei 扫描失败",
                "target_url": target_url,
                "result": {
                    "vulnerable": False,
                    "reason": outcome.get("error") or "Nuclei 扫描失败",
                    "details": outcome,
                },
            }

        vulnerable = bool(outcome.get("vulnerable"))
        total_findings = int(outcome.get("total_findings") or 0)
        reason = (
            f"Nuclei 命中 {total_findings} 条结果"
            if vulnerable
            else "Nuclei 未发现漏洞"
        )
        return {
            "success": True,
            "target_url": target_url,
            "result": {
                "vulnerable": vulnerable,
                "reason": reason,
                "details": {
                    "engine_type": "nuclei",
                    "template_path": template_path,
                    "findings": outcome.get("findings") or [],
                    "total_findings": total_findings,
                    "errors": outcome.get("errors"),
                },
            },
        }

    def _mark_item_running(self, item_id: int):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE batch_task_items
                SET status = 'running', started_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (item_id,),
            )

    def _store_item_result(self, item_id: int, outcome: Dict):
        if self._should_preserve_cancelled(item_id):
            self._store_item_cancelled(item_id, outcome)
            return

        success = bool(outcome.get("success"))
        status = "success" if success else "failed"
        result = outcome.get("result") or {}
        vulnerable = bool(result.get("vulnerable"))
        reason = result.get("reason") or outcome.get("error") or ("检测到漏洞" if vulnerable else "未发现漏洞")
        error = outcome.get("error")
        classification = outcome.get("classification") or classify_execution_outcome(outcome)
        detail_file = self._write_detail_file(item_id, status, vulnerable, outcome)
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE batch_task_items
                SET status = ?, result_json = NULL, vulnerable = ?, reason = ?, detail_file = ?, error = ?,
                    failure_category = ?, failure_code = ?, failure_stage = ?, retryable = ?, finished_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    status,
                    int(vulnerable),
                    reason,
                    detail_file,
                    error,
                    classification.get("failure_category"),
                    classification.get("failure_code"),
                    classification.get("failure_stage"),
                    int(bool(classification.get("retryable"))),
                    item_id,
                ),
            )

    def _store_item_cancelled(self, item_id: int, outcome: Optional[Dict] = None):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE batch_task_items
                SET status = 'cancelled',
                    reason = COALESCE(reason, '任务已取消'),
                    error = COALESCE(error, ?),
                    finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP)
                WHERE id = ?
                """,
                ((outcome or {}).get("error"), item_id),
            )

    def _should_preserve_cancelled(self, item_id: int) -> bool:
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT i.status AS item_status, t.status AS task_status
                FROM batch_task_items i
                JOIN batch_tasks t ON t.id = i.task_id
                WHERE i.id = ?
                """,
                (item_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False
            return row["item_status"] == "cancelled" or row["task_status"] == "cancelled"

    def _refresh_task_stats(self, task_id: int):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN status IN ('success', 'failed', 'cancelled', 'skipped') THEN 1 ELSE 0 END) AS completed_count,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
                    SUM(CASE WHEN vulnerable = 1 THEN 1 ELSE 0 END) AS vulnerable_count
                FROM batch_task_items
                WHERE task_id = ?
                """,
                (task_id,),
            )
            row = cursor.fetchone()
            cursor.execute(
                """
                UPDATE batch_tasks
                SET total_items = ?,
                    completed_items = ?,
                    success_items = ?,
                    failed_items = ?,
                    vulnerable_items = ?
                WHERE id = ?
                """,
                (
                    row["total_count"] or 0,
                    row["completed_count"] or 0,
                    row["success_count"] or 0,
                    row["failed_count"] or 0,
                    row["vulnerable_count"] or 0,
                    task_id,
                ),
            )

    def _finalize_task(self, task_id: int, cancelled: bool):
        self._refresh_task_stats(task_id)
        final_status = "cancelled" if cancelled else "completed"
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE batch_tasks
                SET status = ?, finished_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (final_status, task_id),
            )
            if cancelled:
                cursor.execute(
                    """
                    UPDATE batch_task_items
                    SET status = 'cancelled', finished_at = CURRENT_TIMESTAMP
                    WHERE task_id = ? AND status = 'pending'
                    """,
                    (task_id,),
                )
        self._refresh_task_stats(task_id)

    def _normalize_urls(self, target_urls: List[str]) -> List[str]:
        urls = []
        seen = set()
        for url in target_urls or []:
            cleaned = (url or "").strip()
            if not cleaned:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                urls.append(cleaned)
        return urls

    def _normalize_poc_ids(self, poc_ids: List[int]) -> List[int]:
        normalized = []
        seen = set()
        for poc_id in poc_ids or []:
            try:
                value = int(poc_id)
            except (TypeError, ValueError):
                continue
            if value not in seen:
                seen.add(value)
                normalized.append(value)
        return normalized

    def _validate_pocs(self, poc_ids: List[int]) -> List[Dict]:
        valid = []
        invalid = []
        for poc_id in poc_ids:
            poc = poc_library_service.get_poc_by_id(poc_id)
            if (
                not poc
                or poc.get("verifiable") == 0
                or poc.get("poc_type") == "manual"
                or poc.get("execution_mode") != "url_only"
            ):
                invalid.append(poc_id)
                continue
            valid.append(poc)

        if invalid and not valid:
            raise ValueError(
                f"所选POC不可用于批量执行，仅支持 url_only 类型: {', '.join(map(str, invalid))}"
            )
        return valid

    def _infer_mode(self, url_count: int, poc_count: int) -> str:
        if url_count > 1 and poc_count > 1:
            return "multi_url_multi_poc"
        if url_count > 1:
            return "multi_url_single_poc"
        if poc_count > 1:
            return "single_url_multi_poc"
        return "single_url_single_poc"

    def _serialize_task_row(self, row: Dict) -> Dict:
        config = row.get("config_json")
        if config:
            try:
                row["config_json"] = json.loads(config)
            except json.JSONDecodeError:
                pass
        return row

    def _serialize_item_row(self, row: Dict) -> Dict:
        result_json = row.get("result_json")
        if result_json:
            try:
                row["result_json"] = json.loads(result_json)
            except json.JSONDecodeError:
                pass
        row["has_detail"] = bool(row.get("detail_file") or row.get("result_json"))
        row["vulnerable"] = bool(row.get("vulnerable"))
        row["retryable"] = bool(row.get("retryable"))
        return row

    def _ensure_batch_task_item_columns(self, cursor: sqlite3.Cursor):
        cursor.execute("PRAGMA table_info(batch_tasks)")
        task_columns = {row["name"] for row in cursor.fetchall()}
        if "task_type" not in task_columns:
            cursor.execute("ALTER TABLE batch_tasks ADD COLUMN task_type TEXT NOT NULL DEFAULT 'poc_batch'")

        cursor.execute("PRAGMA table_info(batch_task_items)")
        existing_columns = {row["name"] for row in cursor.fetchall()}
        if "vulnerable" not in existing_columns:
            cursor.execute("ALTER TABLE batch_task_items ADD COLUMN vulnerable INTEGER NOT NULL DEFAULT 0")
        if "reason" not in existing_columns:
            cursor.execute("ALTER TABLE batch_task_items ADD COLUMN reason TEXT")
        if "detail_file" not in existing_columns:
            cursor.execute("ALTER TABLE batch_task_items ADD COLUMN detail_file TEXT")
        if "template_path" not in existing_columns:
            cursor.execute("ALTER TABLE batch_task_items ADD COLUMN template_path TEXT")
        if "failure_category" not in existing_columns:
            cursor.execute("ALTER TABLE batch_task_items ADD COLUMN failure_category TEXT")
        if "failure_code" not in existing_columns:
            cursor.execute("ALTER TABLE batch_task_items ADD COLUMN failure_code TEXT")
        if "failure_stage" not in existing_columns:
            cursor.execute("ALTER TABLE batch_task_items ADD COLUMN failure_stage TEXT")
        if "retryable" not in existing_columns:
            cursor.execute("ALTER TABLE batch_task_items ADD COLUMN retryable INTEGER NOT NULL DEFAULT 0")

    def _backfill_batch_task_item_summaries(self, cursor: sqlite3.Cursor):
        cursor.execute(
            """
            SELECT id, status, error, result_json, vulnerable, reason
            FROM batch_task_items
            WHERE result_json IS NOT NULL
              AND (
                    reason IS NULL OR reason = '' OR vulnerable IS NULL
                    OR failure_category IS NULL OR failure_code IS NULL
                  )
            """
        )
        rows = cursor.fetchall()
        for row in rows:
            summary = self._extract_summary_from_outcome(
                self._safe_load_json(row["result_json"]) or {},
                row["status"],
                row["error"],
            )
            classification = classify_execution_outcome(self._safe_load_json(row["result_json"]) or {})
            cursor.execute(
                """
                UPDATE batch_task_items
                SET vulnerable = COALESCE(vulnerable, ?),
                    reason = COALESCE(reason, ?),
                    failure_category = COALESCE(failure_category, ?),
                    failure_code = COALESCE(failure_code, ?),
                    failure_stage = COALESCE(failure_stage, ?),
                    retryable = CASE
                        WHEN retryable IS NULL OR retryable = 0 THEN ?
                        ELSE retryable
                    END
                WHERE id = ?
                """,
                (
                    summary["vulnerable"],
                    summary["reason"],
                    classification.get("failure_category"),
                    classification.get("failure_code"),
                    classification.get("failure_stage"),
                    int(bool(classification.get("retryable"))),
                    row["id"],
                ),
            )

    def _extract_summary_from_outcome(self, outcome: Dict, status: str, error: Optional[str]) -> Dict:
        result = outcome.get("result") or {}
        vulnerable = bool(result.get("vulnerable"))
        reason = result.get("reason") or error

        if not reason:
            if status == "failed":
                reason = "执行失败"
            elif vulnerable:
                reason = "检测到漏洞"
            elif status == "cancelled":
                reason = "任务已取消"
            else:
                reason = "未发现漏洞"

        return {"vulnerable": int(vulnerable), "reason": reason}

    def _write_detail_file(self, item_id: int, status: str, vulnerable: bool, outcome: Dict) -> Optional[str]:
        if status != "failed" and not vulnerable:
            return None

        item_dir = self.batch_results_dir / f"task_{self._get_task_id_for_item(item_id)}"
        item_dir.mkdir(parents=True, exist_ok=True)
        detail_path = item_dir / f"item_{item_id}.json"
        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(outcome, f, ensure_ascii=False, indent=2)
        return str(detail_path)

    def _get_task_id_for_item(self, item_id: int) -> int:
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT task_id FROM batch_task_items WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"批量子任务不存在: {item_id}")
            return row["task_id"]

    def _safe_load_json(self, raw_value: Optional[str]) -> Optional[Dict]:
        if not raw_value:
            return None
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return None

    def _normalize_template_paths(self, template_paths: List[str]) -> List[str]:
        normalized = []
        seen = set()
        for template_path in template_paths or []:
            path = str(template_path or "").strip().replace("\\", "/")
            if not path or path in seen:
                continue
            full_path = nuclei_service.templates_dir / path
            if not full_path.exists():
                continue
            seen.add(path)
            normalized.append(path)
        return normalized

    def build_task_report_payload(self, task_id: int) -> Dict:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("批量任务不存在")

        items = self.get_task_items(task_id=task_id, limit=self.MAX_TASK_ITEMS)["items"]
        hit_count = task.get("vulnerable_items", 0) or 0
        exception_count = task.get("failed_items", 0) or 0
        miss_count = max((task.get("success_items", 0) or 0) - hit_count, 0)
        config = task.get("config_json") or {}
        unit_label = "模板" if task.get("task_type") == "nuclei_scan" else "POC"

        return {
            "task": task,
            "summary": {
                "mode": task.get("mode"),
                "task_type": task.get("task_type"),
                "status": task.get("status"),
                "url_count": config.get("url_count", 0),
                "poc_count": config.get("poc_count", 0),
                "unit_count": config.get("template_count", config.get("poc_count", 0)),
                "unit_label": unit_label,
                "total_items": task.get("total_items", 0),
                "completed_items": task.get("completed_items", 0),
                "hit_items": hit_count,
                "miss_items": miss_count,
                "exception_items": exception_count,
                "created_at": task.get("created_at"),
                "started_at": task.get("started_at"),
                "finished_at": task.get("finished_at"),
            },
            "items": items,
        }

    def export_task_report(self, task_id: int, report_format: str) -> Tuple[str, str, bytes]:
        payload = self.build_task_report_payload(task_id)
        normalized_format = (report_format or "html").lower()

        if normalized_format == "json":
            content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            return (
                f"batch_task_{task_id}_report.json",
                "application/json; charset=utf-8",
                content,
            )

        if normalized_format == "txt":
            content = self._render_text_report(payload).encode("utf-8")
            return (
                f"batch_task_{task_id}_report.txt",
                "text/plain; charset=utf-8",
                content,
            )

        if normalized_format == "html":
            content = self._render_html_report(payload).encode("utf-8")
            return (
                f"batch_task_{task_id}_report.html",
                "text/html; charset=utf-8",
                content,
            )

        raise ValueError("不支持的报告格式，仅支持 html/json/txt")

    def _render_text_report(self, payload: Dict) -> str:
        summary = payload["summary"]
        task = payload["task"]
        lines = [
            f"批量检测报告 - 任务 #{task['id']}",
            "=" * 72,
            f"状态: {task.get('status')}",
            f"模式: {summary.get('mode')}",
            f"任务类型: {'Nuclei 扫描' if summary.get('task_type') == 'nuclei_scan' else 'POC 批量检测'}",
            f"URL 数量: {summary.get('url_count')}",
            f"{summary.get('unit_label', 'POC')} 数量: {summary.get('unit_count')}",
            f"子任务总数: {summary.get('total_items')}",
            f"已完成: {summary.get('completed_items')}",
            f"命中: {summary.get('hit_items')}",
            f"未命中: {summary.get('miss_items')}",
            f"异常: {summary.get('exception_items')}",
            f"创建时间: {summary.get('created_at') or '-'}",
            f"开始时间: {summary.get('started_at') or '-'}",
            f"完成时间: {summary.get('finished_at') or '-'}",
            "",
            "子任务结果",
            "-" * 72,
        ]

        for item in payload["items"]:
            target_name = item.get("template_path") or item.get("vuln_name") or f"POC-{item.get('poc_id')}"
            lines.extend([
                f"[{self._get_item_status_label(item)}] {item.get('target_url')}",
                f"{'模板' if item.get('engine_type') == 'nuclei' else 'POC'}: {target_name}",
                f"命中: {'是' if item.get('vulnerable') else '否'}",
                f"依据: {item.get('reason') or '-'}",
                f"错误: {item.get('error') or '-'}",
                "-" * 72,
            ])

        return "\n".join(lines)

    def _render_html_report(self, payload: Dict) -> str:
        summary = payload["summary"]
        task = payload["task"]
        rows = []
        for item in payload["items"]:
            rows.append(
                f"""
                <tr>
                    <td>{escape(str(item.get('target_url') or '-'))}</td>
                    <td>{escape(str(item.get('template_path') or item.get('vuln_name') or f"POC-{item.get('poc_id')}"))}</td>
                    <td>{escape(self._get_item_status_label(item))}</td>
                    <td>{"是" if item.get("vulnerable") else "否"}</td>
                    <td>{escape(str(item.get('reason') or '-'))}</td>
                    <td>{escape(str(item.get('error') or '-'))}</td>
                </tr>
                """
            )

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>批量检测报告 #{task['id']}</title>
    <style>
        body {{ font-family: "Segoe UI", "PingFang SC", sans-serif; margin: 24px; color: #1f2937; }}
        h1 {{ margin-bottom: 8px; }}
        .meta {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 20px 0; }}
        .card {{ background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px; }}
        .label {{ font-size: 12px; color: #6b7280; margin-bottom: 6px; }}
        .value {{ font-size: 20px; font-weight: 700; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
        th, td {{ border: 1px solid #e5e7eb; padding: 10px; text-align: left; vertical-align: top; }}
        th {{ background: #eef2ff; }}
        .hint {{ color: #6b7280; font-size: 13px; }}
    </style>
</head>
<body>
    <h1>批量检测报告 #{task['id']}</h1>
    <div class="hint">状态：{escape(str(task.get('status') or '-'))} ｜ 模式：{escape(str(summary.get('mode') or '-'))} ｜ 类型：{"Nuclei 扫描" if summary.get('task_type') == 'nuclei_scan' else "POC 批量检测"}</div>
    <div class="meta">
        <div class="card"><div class="label">URL 数量</div><div class="value">{summary.get('url_count', 0)}</div></div>
        <div class="card"><div class="label">{summary.get('unit_label', 'POC')} 数量</div><div class="value">{summary.get('unit_count', 0)}</div></div>
        <div class="card"><div class="label">命中</div><div class="value">{summary.get('hit_items', 0)}</div></div>
        <div class="card"><div class="label">异常</div><div class="value">{summary.get('exception_items', 0)}</div></div>
    </div>
    <div class="hint">创建时间：{escape(str(summary.get('created_at') or '-'))} ｜ 完成时间：{escape(str(summary.get('finished_at') or '-'))}</div>
    <table>
        <thead>
            <tr>
                <th>URL</th>
                <th>POC</th>
                <th>状态</th>
                <th>命中</th>
                <th>判断依据</th>
                <th>错误信息</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
</body>
</html>"""

    def _get_item_status_label(self, item: Dict) -> str:
        if item.get("status") == "failed":
            return "异常"
        if item.get("vulnerable"):
            return "命中"
        if item.get("status") == "success":
            return "未命中"
        if item.get("status") == "cancelled":
            return "已取消"
        return str(item.get("status") or "未知")


batch_task_service = BatchTaskService()
