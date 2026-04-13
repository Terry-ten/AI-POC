"""
POC库管理服务

功能：
1. POC的保存、查询、搜索
2. 支持多种POC类型（Python、Nuclei等）
3. POC执行引擎路由
4. 统计和管理功能
"""

import sqlite3
import hashlib
import json
import importlib.util
import inspect
import sys
import time
import logging
import types
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse

# 配置日志
logger = logging.getLogger(__name__)

from services.nuclei_service import nuclei_service
from services.http_runtime import (
    HTTPRuntimeClient,
    create_http_client,
    get_http_client,
    http_request,
    send_raw_http,
)
from services.dependency_checker import check_python_code_dependencies, check_python_file_dependencies
from services.failure_classifier import classify_execution_outcome
from services.oob_service import oob_service

class PocLibraryService:
    DEFAULT_HTTP_TIMEOUT = 6
    NETWORK_ERROR_KEYWORDS = (
        "connection refused",
        "name or service not known",
        "failed to establish a new connection",
        "temporary failure in name resolution",
        "max retries exceeded",
        "read timed out",
        "connect timeout",
        "timed out",
        "nodename nor servname provided",
        "getaddrinfo failed",
        "connection aborted",
        "connection reset",
        "proxyerror",
        "newconnectionerror",
        "dns",
        "timeout",
    )

    def __init__(self):
        """初始化POC库服务"""
        self.base_dir = Path(__file__).parent.parent
        self.pocs_dir = self.base_dir / "pocs"
        self.db_path = self.pocs_dir / "poc_library.db"

        # 初始化目录和数据库
        self.init_storage()
        self.init_database()

    @contextmanager
    def get_db_connection(self):
        """数据库连接上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_storage(self):
        """初始化文件存储结构"""
        # 创建主目录
        self.pocs_dir.mkdir(exist_ok=True)

        # 创建子目录
        (self.pocs_dir / "python").mkdir(exist_ok=True)
        (self.pocs_dir / "nuclei").mkdir(exist_ok=True)
        (self.pocs_dir / "metadata").mkdir(exist_ok=True)

        logger.info(f"POC库目录初始化完成: {self.pocs_dir}")

    def init_database(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建poc_records表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS poc_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vuln_type TEXT NOT NULL,
                vuln_name TEXT NOT NULL,
                vuln_description TEXT,
                poc_type TEXT DEFAULT 'python',
                poc_file_path TEXT NOT NULL,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                tags TEXT,
                metadata TEXT,
                verifiable BOOLEAN DEFAULT 1,
                manual_steps TEXT
            )
        """)

        # 检查并添加新字段（用于数据库迁移）
        cursor.execute("PRAGMA table_info(poc_records)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'verifiable' not in columns:
            cursor.execute("ALTER TABLE poc_records ADD COLUMN verifiable BOOLEAN DEFAULT 1")
            logger.info("Migration: 添加 verifiable 字段")

        if 'manual_steps' not in columns:
            cursor.execute("ALTER TABLE poc_records ADD COLUMN manual_steps TEXT")
            logger.info("Migration: 添加 manual_steps 字段")

        if 'explanation' not in columns:
            cursor.execute("ALTER TABLE poc_records ADD COLUMN explanation TEXT")
            logger.info("Migration: 添加 explanation 字段")

        if 'execution_mode' not in columns:
            cursor.execute("ALTER TABLE poc_records ADD COLUMN execution_mode TEXT")
            logger.info("Migration: 添加 execution_mode 字段")

        if 'verification_method' not in columns:
            cursor.execute("ALTER TABLE poc_records ADD COLUMN verification_method TEXT")
            logger.info("Migration: 添加 verification_method 字段")

        if 'input_schema' not in columns:
            cursor.execute("ALTER TABLE poc_records ADD COLUMN input_schema TEXT")
            logger.info("Migration: 添加 input_schema 字段")

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vuln_type ON poc_records(vuln_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_poc_type ON poc_records(poc_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_create_time ON poc_records(create_time DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_verifiable ON poc_records(verifiable)")

        conn.commit()
        conn.close()

        logger.info(f"POC库数据库初始化完成: {self.db_path}")

    def save_poc(self,
                 vuln_type: str,
                 vuln_info: str,
                 vuln_name: str = None,
                 poc_code: str = None,
                 explanation: str = "",
                 poc_type: str = "python",
                 tags: List[str] = None,
                 metadata: dict = None,
                 verifiable: bool = True,
                 manual_steps: dict = None,
                 execution_mode: Optional[str] = None,
                 verification_method: Optional[str] = None,
                 input_schema: Optional[List[Dict]] = None) -> int:
        """
        保存POC到库中

        Args:
            vuln_type: 漏洞类型（如sqli, xss, rce等）
            vuln_info: 漏洞描述信息
            poc_code: POC代码内容（可验证时必需）
            explanation: POC说明
            poc_type: POC类型（python/nuclei/manual）
            tags: 标签列表
            metadata: 元数据
            verifiable: 是否可自动化验证
            manual_steps: 人工操作指南（不可验证时必需）

        Returns:
            int: POC记录ID
        """
        normalized_vuln_name = self._normalize_vuln_name(vuln_name, vuln_type, vuln_info)
        file_stem = self._build_file_stem(normalized_vuln_name)
        resolved_execution_mode = execution_mode or ("url_only" if verifiable else "manual_guide")
        resolved_verification_method = verification_method or ("direct" if verifiable else "manual")

        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_suffix = hashlib.md5(vuln_info.encode()).hexdigest()[:6]

        if verifiable:
            # 可自动化验证：保存POC代码
            if not poc_code:
                raise ValueError("可验证的POC必须提供poc_code")

            if poc_type == "python":
                file_name = f"{file_stem}_{timestamp}_{hash_suffix}.py"
                poc_file_path = self.pocs_dir / "python" / file_name

                # 保存Python POC文件
                with open(poc_file_path, 'w', encoding='utf-8') as f:
                    f.write(poc_code)

                # 保存元数据文件
                metadata_file = self.pocs_dir / "metadata" / f"{file_stem}_{timestamp}_{hash_suffix}.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "vuln_type": vuln_type,
                        "vuln_name": normalized_vuln_name,
                        "vuln_info": vuln_info,
                        "explanation": explanation,
                        "execution_mode": resolved_execution_mode,
                        "verification_method": resolved_verification_method,
                        "input_schema": input_schema,
                        "create_time": timestamp,
                        "tags": tags or [],
                        "metadata": metadata or {}
                    }, f, ensure_ascii=False, indent=2)

            elif poc_type == "nuclei":
                file_name = f"{file_stem}_{timestamp}_{hash_suffix}.yaml"
                poc_file_path = self.pocs_dir / "nuclei" / file_name

                # 保存Nuclei模板
                with open(poc_file_path, 'w', encoding='utf-8') as f:
                    f.write(poc_code)

            else:
                raise ValueError(f"不支持的POC类型: {poc_type}")
        else:
            # 不可自动化验证：保存人工操作指南
            if not manual_steps:
                raise ValueError("不可验证的POC必须提供manual_steps")

            poc_type = "manual"  # 设置为manual类型
            file_name = f"{file_stem}_{timestamp}_{hash_suffix}.json"
            poc_file_path = self.pocs_dir / "metadata" / file_name

            # 保存人工操作指南
            with open(poc_file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "vuln_type": vuln_type,
                    "vuln_name": normalized_vuln_name,
                    "vuln_info": vuln_info,
                    "explanation": explanation,
                    "execution_mode": resolved_execution_mode,
                    "verification_method": resolved_verification_method,
                    "input_schema": input_schema,
                    "create_time": timestamp,
                    "tags": tags or [],
                    "metadata": metadata or {},
                    "manual_steps": manual_steps
                }, f, ensure_ascii=False, indent=2)

        # 插入数据库记录
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO poc_records
            (vuln_type, vuln_name, vuln_description, poc_type, poc_file_path, tags, metadata, verifiable, manual_steps, explanation, execution_mode, verification_method, input_schema)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vuln_type,
            normalized_vuln_name,
            vuln_info,
            poc_type,
            str(poc_file_path),
            ",".join(tags) if tags else "",
            json.dumps(metadata or {}, ensure_ascii=False),
            1 if verifiable else 0,
            json.dumps(manual_steps, ensure_ascii=False) if manual_steps else None,
            explanation,
            resolved_execution_mode,
            resolved_verification_method,
            json.dumps(input_schema, ensure_ascii=False) if input_schema else None,
        ))

        poc_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"POC已保存到库: ID={poc_id}, 文件={poc_file_path.name}")

        return poc_id

    def _normalize_vuln_name(self, vuln_name: Optional[str], vuln_type: str, vuln_info: str) -> str:
        """标准化漏洞名称，优先保留产品/框架信息。"""
        if vuln_name:
            cleaned = " ".join(vuln_name.strip().split())
            if cleaned:
                return cleaned[:120]

        first_line = next((line.strip("# ").strip() for line in vuln_info.splitlines() if line.strip()), "")
        if first_line:
            return first_line[:120]

        return vuln_type or "unknown"

    def _build_file_stem(self, vuln_name: str) -> str:
        """将漏洞名称转换为适合文件名的前缀。"""
        cleaned = []
        for ch in vuln_name:
            if ch.isalnum() or ch in ("-", "_"):
                cleaned.append(ch)
            elif ch in (" ", ".", "/", "\\", ":", "|", "(", ")", "[", "]"):
                cleaned.append("_")
        stem = "".join(cleaned).strip("_")
        while "__" in stem:
            stem = stem.replace("__", "_")
        return (stem or "poc")[:80]

    def get_poc_by_id(self, poc_id: int) -> Optional[Dict]:
        """
        根据ID获取POC记录

        Args:
            poc_id: POC记录ID

        Returns:
            Dict: POC记录信息，如果不存在返回None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM poc_records WHERE id = ?", (poc_id,))
        row = cursor.fetchone()
        conn.close()

        return self._serialize_poc_row(dict(row)) if row else None

    def search_pocs(self,
                    vuln_type: str = None,
                    poc_type: str = None,
                    keyword: str = None,
                    tags: List[str] = None,
                    verifiable: bool = None,
                    limit: int = 50,
                    offset: int = 0) -> List[Dict]:
        """
        搜索POC

        Args:
            vuln_type: 漏洞类型过滤
            poc_type: POC类型过滤（python/nuclei/manual）
            keyword: 关键词搜索（在名称和描述中搜索）
            tags: 标签过滤
            verifiable: 是否可验证过滤（True/False/None）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Dict]: POC记录列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM poc_records WHERE 1=1"
        params = []

        if vuln_type:
            query += " AND vuln_type = ?"
            params.append(vuln_type)

        if poc_type:
            query += " AND poc_type = ?"
            params.append(poc_type)

        if keyword:
            query += " AND (vuln_name LIKE ? OR vuln_description LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        if tags:
            for tag in tags:
                query += " AND tags LIKE ?"
                params.append(f"%{tag}%")

        if verifiable is not None:
            query += " AND verifiable = ?"
            params.append(1 if verifiable else 0)

        query += " ORDER BY create_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._serialize_poc_row(dict(row)) for row in rows]

    def get_all_vuln_types(self) -> List[Dict]:
        """获取所有漏洞类型及其统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT vuln_type, COUNT(*) as count
            FROM poc_records
            GROUP BY vuln_type
            ORDER BY count DESC
        """)

        results = [{"vuln_type": row[0], "count": row[1]} for row in cursor.fetchall()]
        conn.close()

        return results

    def get_statistics(self) -> Dict:
        """获取POC库统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 总POC数量
        cursor.execute("SELECT COUNT(*) FROM poc_records")
        total_pocs = cursor.fetchone()[0]

        # 各类型POC数量
        cursor.execute("SELECT poc_type, COUNT(*) FROM poc_records GROUP BY poc_type")
        type_stats = {row[0]: row[1] for row in cursor.fetchall()}

        # 最近使用的POC
        cursor.execute("SELECT id, vuln_name, last_used FROM poc_records WHERE last_used IS NOT NULL ORDER BY last_used DESC LIMIT 5")
        recent_used = [{"id": row[0], "name": row[1], "last_used": row[2]} for row in cursor.fetchall()]

        conn.close()

        return {
            "total_pocs": total_pocs,
            "python_pocs": type_stats.get("python", 0),
            "nuclei_pocs": type_stats.get("nuclei", 0),
            "recent_used": recent_used
        }

    def _serialize_poc_row(self, row: Dict) -> Dict:
        if row.get("manual_steps"):
            try:
                row["manual_steps"] = json.loads(row["manual_steps"])
            except json.JSONDecodeError:
                pass

        if row.get("metadata"):
            try:
                row["metadata"] = json.loads(row["metadata"])
            except json.JSONDecodeError:
                pass

        if row.get("input_schema"):
            try:
                row["input_schema"] = json.loads(row["input_schema"])
            except json.JSONDecodeError:
                pass
        else:
            row["input_schema"] = None

        if not row.get("execution_mode"):
            row["execution_mode"] = "url_only" if row.get("verifiable") else "manual_guide"

        if not row.get("verification_method"):
            row["verification_method"] = "direct" if row.get("verifiable") else "manual"

        return row

    def execute_poc(self, poc_id: int, target_url: str, runtime_params: Optional[Dict[str, Any]] = None) -> Dict:
        """
        执行指定的POC

        Args:
            poc_id: POC记录ID
            target_url: 目标URL

        Returns:
            Dict: 执行结果
        """
        poc_record = self.get_poc_by_id(poc_id)
        if not poc_record:
            result = {"success": False, "error": "POC不存在"}
            result["classification"] = classify_execution_outcome(result)
            return result

        verification_method = (poc_record.get("verification_method") or "").lower()
        if verification_method == "oob":
            runtime_status = oob_service.get_runtime_status()
            if not runtime_status["runtime_ready"]:
                result = {
                    "success": False,
                    "error": runtime_status["runtime_error"] or "OOB 运行环境不可用",
                    "result": {
                        "vulnerable": False,
                        "reason": "OOB 运行环境不可用",
                        "details": runtime_status,
                    },
                }
                result["classification"] = classify_execution_outcome(result)
                return result

        # 更新最后使用时间
        self._update_last_used(poc_id)

        # 根据POC类型选择执行引擎
        try:
            if poc_record['poc_type'] == 'python':
                result = self._execute_python_poc(
                    poc_record['poc_file_path'],
                    target_url,
                    runtime_params=runtime_params,
                )
            elif poc_record['poc_type'] == 'nuclei':
                status = nuclei_service.check_nuclei_available()
                if not status.get("available"):
                    result = {"success": False, "error": status.get("error", "Nuclei引擎未安装或不可用")}
                else:
                    nuclei_result = nuclei_service.scan_single(target_url, poc_record['poc_file_path'])
                    result = self._normalize_nuclei_result(nuclei_result)
            else:
                result = {"success": False, "error": f"不支持的POC类型: {poc_record['poc_type']}"}

            result["classification"] = classify_execution_outcome(result)
            return result

        except Exception as e:
            result = {"success": False, "error": f"执行POC时出错: {str(e)}"}
            result["classification"] = classify_execution_outcome(result)
            return result

    def _normalize_nuclei_result(self, nuclei_result: Dict) -> Dict:
        """
        将 Nuclei 扫描结果转换为 POC 库统一返回结构

        Returns:
            Dict: 与 Python POC 一致的 success/target_url/result 结构
        """
        if not nuclei_result.get("success"):
            return nuclei_result

        findings = nuclei_result.get("findings", [])
        vulnerable = nuclei_result.get("vulnerable", False)

        if vulnerable and findings:
            first_finding = findings[0]
            reason = f"Nuclei检测到漏洞: {first_finding.get('template_name') or first_finding.get('template_id') or '未知模板'}"
        else:
            reason = "Nuclei未检测到漏洞"

        return {
            "success": True,
            "target_url": nuclei_result.get("target_url"),
            "result": {
                "vulnerable": vulnerable,
                "reason": reason,
                "details": {
                    "total_findings": nuclei_result.get("total_findings", 0),
                    "findings": findings,
                    "errors": nuclei_result.get("errors"),
                    "warnings": nuclei_result.get("warnings")
                }
            }
        }

    def _execute_python_poc(
        self,
        poc_file_path: str,
        target_url: str,
        runtime_params: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        执行Python POC

        Args:
            poc_file_path: POC文件路径
            target_url: 目标URL

        Returns:
            Dict: 执行结果
        """
        try:
            # 标准化URL
            normalized_url = self._normalize_url(target_url)

            # 检查文件是否存在
            poc_path = Path(poc_file_path)
            if not poc_path.exists():
                return {"success": False, "error": f"POC文件不存在: {poc_file_path}"}

            runtime_params = runtime_params or {}

            dependency_check = check_python_file_dependencies(poc_path)
            if dependency_check.get("missing"):
                missing_modules = ", ".join(dependency_check["missing"])
                return {
                    "success": False,
                    "target_url": normalized_url,
                    "error": f"缺少依赖: {missing_modules}",
                    "result": {
                        "vulnerable": False,
                        "reason": "执行环境缺少依赖",
                        "details": dependency_check,
                    }
                }

            # 动态导入POC模块
            module_name = f"poc_module_{int(time.time() * 1000)}"
            spec = importlib.util.spec_from_file_location(module_name, poc_path)
            poc_module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = poc_module

            helper_module = types.ModuleType("oob_runtime")
            helper_module.create_client = oob_service.create_client
            helper_module.get_oob_client = oob_service.create_client
            sys.modules["oob_runtime"] = helper_module

            http_helper_module = types.ModuleType("http_runtime")
            http_helper_module.HTTPRuntimeClient = HTTPRuntimeClient
            http_helper_module.create_http_client = create_http_client
            http_helper_module.get_http_client = get_http_client
            http_helper_module.http_request = http_request
            http_helper_module.send_raw_http = send_raw_http
            sys.modules["http_runtime"] = http_helper_module

            poc_module.create_oob_client = oob_service.create_client
            poc_module.get_oob_client = oob_service.create_client
            poc_module.HTTPRuntimeClient = HTTPRuntimeClient
            poc_module.create_http_client = create_http_client
            poc_module.get_http_client = get_http_client
            poc_module.http_request = http_request
            poc_module.send_raw_http = send_raw_http
            poc_module.runtime_params = runtime_params
            poc_module.runtime_input = runtime_params
            poc_module.input_params = runtime_params
            poc_module.get_runtime_param = lambda name, default=None: runtime_params.get(name, default)
            spec.loader.exec_module(poc_module)

            try:
                # 检查scan函数是否存在
                if not hasattr(poc_module, 'scan'):
                    raise AttributeError("POC脚本中未找到scan函数")

                # 执行scan函数
                scan = poc_module.scan
                timeout_restore = self._patch_requests_timeout()
                try:
                    result = self._invoke_scan(scan, normalized_url, runtime_params)
                finally:
                    timeout_restore()
            finally:
                # 清理模块（避免内存泄漏）
                if module_name in sys.modules:
                    del sys.modules[module_name]
                if "oob_runtime" in sys.modules:
                    del sys.modules["oob_runtime"]
                if "http_runtime" in sys.modules:
                    del sys.modules["http_runtime"]

            # 验证返回格式
            if not isinstance(result, dict):
                result = {
                    "vulnerable": False,
                    "reason": "扫描函数返回格式不正确",
                    "details": str(result)
                }

            if self._is_network_failure_result(result):
                return {
                    "success": False,
                    "target_url": normalized_url,
                    "error": result.get("reason") or self._extract_network_error_message(result),
                    "result": {
                        "vulnerable": False,
                        "reason": result.get("reason") or "目标不可达或请求超时",
                        "details": result.get("details")
                    }
                }

            return {
                "success": True,
                "target_url": normalized_url,
                "result": result
            }

        except Exception as e:
            return {
                "success": False,
                "target_url": target_url,
                "error": f"{type(e).__name__}: {str(e)}",
                "result": {
                    "vulnerable": False,
                    "reason": "执行POC时发生错误",
                    "details": str(e)
                }
            }

    def check_poc_dependencies(self, code: str) -> Dict[str, Any]:
        """对生成后的 Python POC 做最小依赖预检。"""
        return check_python_code_dependencies(code)

    def _invoke_scan(self, scan, normalized_url: str, runtime_params: Optional[Dict[str, Any]] = None):
        """兼容旧版 scan(url) 与新版 scan(url, runtime_params) 调用方式。"""
        runtime_params = runtime_params or {}
        signature = inspect.signature(scan)
        parameters = list(signature.parameters.values())

        if not parameters:
            return scan()

        if "runtime_params" in signature.parameters:
            return scan(normalized_url, runtime_params=runtime_params)

        if "params" in signature.parameters:
            return scan(normalized_url, params=runtime_params)

        positional_params = [
            parameter for parameter in parameters
            if parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        has_varargs = any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters)

        if len(positional_params) >= 2 or has_varargs:
            return scan(normalized_url, runtime_params)

        return scan(normalized_url)

    def _patch_requests_timeout(self):
        """为未显式设置 timeout 的 requests 调用注入默认超时。"""
        try:
            import requests
        except ImportError:
            return lambda: None

        original_request = requests.sessions.Session.request
        default_timeout = self.DEFAULT_HTTP_TIMEOUT

        def request_with_timeout(session, method, url, **kwargs):
            kwargs.setdefault("timeout", default_timeout)
            return original_request(session, method, url, **kwargs)

        requests.sessions.Session.request = request_with_timeout

        def restore():
            requests.sessions.Session.request = original_request

        return restore

    def _is_network_failure_result(self, result: Dict) -> bool:
        if result.get("vulnerable"):
            return False

        details = result.get("details")
        reason = result.get("reason")
        message = self._extract_network_error_message({"reason": reason, "details": details})
        return bool(message)

    def _extract_network_error_message(self, payload: Dict) -> Optional[str]:
        candidates = [payload.get("reason"), payload.get("details")]
        for value in candidates:
            if value is None:
                continue
            if isinstance(value, dict):
                text = json.dumps(value, ensure_ascii=False).lower()
            else:
                text = str(value).lower()

            if isinstance(value, BaseException):
                return str(value)

            for keyword in self.NETWORK_ERROR_KEYWORDS:
                if keyword in text:
                    return str(value)
        return None

    def _normalize_url(self, url: str) -> str:
        """
        标准化URL格式

        Args:
            url: 原始URL

        Returns:
            str: 标准化后的URL（http(s)://host/或http(s)://host:port/）
        """
        # 如果没有协议，默认添加http://
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        # 解析URL
        parsed = urlparse(url)
        scheme = parsed.scheme
        netloc = parsed.netloc

        # 保持原始URL的端口设置，不自动添加默认端口

        # 构建标准化URL（确保以/结尾）
        normalized_url = f"{scheme}://{netloc}/"

        return normalized_url

    def _update_last_used(self, poc_id: int):
        """更新POC最后使用时间"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE poc_records SET last_used = CURRENT_TIMESTAMP WHERE id = ?",
            (poc_id,)
        )
        conn.commit()
        conn.close()

    def delete_poc(self, poc_id: int) -> bool:
        """
        删除POC

        Args:
            poc_id: POC记录ID

        Returns:
            bool: 是否删除成功
        """
        poc_record = self.get_poc_by_id(poc_id)
        if not poc_record:
            return False

        try:
            # 删除文件
            poc_file = Path(poc_record['poc_file_path'])
            if poc_file.exists():
                poc_file.unlink()

            # 删除元数据文件（如果存在）
            metadata_file = self.pocs_dir / "metadata" / (poc_file.stem + ".json")
            if metadata_file.exists():
                metadata_file.unlink()

            # 删除数据库记录
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM poc_records WHERE id = ?", (poc_id,))
            conn.commit()
            conn.close()

            logger.info(f"POC已删除: ID={poc_id}")
            return True

        except FileNotFoundError as e:
            logger.error(f"删除POC失败 - 文件不存在: {str(e)}")
            return False
        except PermissionError as e:
            logger.error(f"删除POC失败 - 权限不足: {str(e)}")
            return False
        except sqlite3.Error as e:
            logger.error(f"删除POC失败 - 数据库错误: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"删除POC失败 - 未知错误: {str(e)}")
            return False


# 创建全局实例
poc_library_service = PocLibraryService()
