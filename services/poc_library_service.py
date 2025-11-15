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
import shutil
import importlib.util
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse

# 导入Nuclei引擎
try:
    from services.nuclei_engine import nuclei_engine
    NUCLEI_AVAILABLE = nuclei_engine.is_available
except ImportError:
    NUCLEI_AVAILABLE = False
    nuclei_engine = None

class PocLibraryService:
    def __init__(self):
        """初始化POC库服务"""
        self.base_dir = Path(__file__).parent.parent
        self.pocs_dir = self.base_dir / "pocs"
        self.db_path = self.pocs_dir / "poc_library.db"

        # 初始化目录和数据库
        self.init_storage()
        self.init_database()

    def init_storage(self):
        """初始化文件存储结构"""
        # 创建主目录
        self.pocs_dir.mkdir(exist_ok=True)

        # 创建子目录
        (self.pocs_dir / "python").mkdir(exist_ok=True)
        (self.pocs_dir / "nuclei").mkdir(exist_ok=True)
        (self.pocs_dir / "metadata").mkdir(exist_ok=True)

        print(f"[OK] POC库目录初始化完成: {self.pocs_dir}")

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
            print("[Migration] 添加 verifiable 字段")

        if 'manual_steps' not in columns:
            cursor.execute("ALTER TABLE poc_records ADD COLUMN manual_steps TEXT")
            print("[Migration] 添加 manual_steps 字段")

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vuln_type ON poc_records(vuln_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_poc_type ON poc_records(poc_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_create_time ON poc_records(create_time DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_verifiable ON poc_records(verifiable)")

        conn.commit()
        conn.close()

        print(f"[OK] POC库数据库初始化完成: {self.db_path}")

    def save_poc(self,
                 vuln_type: str,
                 vuln_info: str,
                 poc_code: str = None,
                 explanation: str = "",
                 poc_type: str = "python",
                 tags: List[str] = None,
                 metadata: dict = None,
                 verifiable: bool = True,
                 manual_steps: dict = None) -> int:
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
        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_suffix = hashlib.md5(vuln_info.encode()).hexdigest()[:6]

        if verifiable:
            # 可自动化验证：保存POC代码
            if not poc_code:
                raise ValueError("可验证的POC必须提供poc_code")

            if poc_type == "python":
                file_name = f"{vuln_type}_{timestamp}_{hash_suffix}.py"
                poc_file_path = self.pocs_dir / "python" / file_name

                # 保存Python POC文件
                with open(poc_file_path, 'w', encoding='utf-8') as f:
                    f.write(poc_code)

                # 保存元数据文件
                metadata_file = self.pocs_dir / "metadata" / f"{vuln_type}_{timestamp}_{hash_suffix}.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "vuln_type": vuln_type,
                        "vuln_info": vuln_info,
                        "explanation": explanation,
                        "create_time": timestamp,
                        "tags": tags or [],
                        "metadata": metadata or {}
                    }, f, ensure_ascii=False, indent=2)

            elif poc_type == "nuclei":
                file_name = f"{vuln_type}_{timestamp}_{hash_suffix}.yaml"
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
            file_name = f"{vuln_type}_{timestamp}_{hash_suffix}.json"
            poc_file_path = self.pocs_dir / "metadata" / file_name

            # 保存人工操作指南
            with open(poc_file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "vuln_type": vuln_type,
                    "vuln_info": vuln_info,
                    "explanation": explanation,
                    "create_time": timestamp,
                    "tags": tags or [],
                    "metadata": metadata or {},
                    "manual_steps": manual_steps
                }, f, ensure_ascii=False, indent=2)

        # 插入数据库记录
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        vuln_name = f"{vuln_type}_{timestamp}"

        cursor.execute("""
            INSERT INTO poc_records
            (vuln_type, vuln_name, vuln_description, poc_type, poc_file_path, tags, metadata, verifiable, manual_steps)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vuln_type,
            vuln_name,
            vuln_info,
            poc_type,
            str(poc_file_path),
            ",".join(tags) if tags else "",
            json.dumps(metadata or {}, ensure_ascii=False),
            1 if verifiable else 0,
            json.dumps(manual_steps, ensure_ascii=False) if manual_steps else None
        ))

        poc_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"[OK] POC已保存到库: ID={poc_id}, 文件={poc_file_path.name}")

        return poc_id

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

        return dict(row) if row else None

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

        return [dict(row) for row in rows]

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

    def execute_poc(self, poc_id: int, target_url: str) -> Dict:
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
            return {"success": False, "error": "POC不存在"}

        # 更新最后使用时间
        self._update_last_used(poc_id)

        # 根据POC类型选择执行引擎
        try:
            if poc_record['poc_type'] == 'python':
                result = self._execute_python_poc(poc_record['poc_file_path'], target_url)
            elif poc_record['poc_type'] == 'nuclei':
                if not NUCLEI_AVAILABLE or nuclei_engine is None:
                    result = {"success": False, "error": "Nuclei引擎未安装或不可用"}
                else:
                    result = nuclei_engine.execute(poc_record['poc_file_path'], target_url)
            else:
                result = {"success": False, "error": f"不支持的POC类型: {poc_record['poc_type']}"}

            return result

        except Exception as e:
            return {"success": False, "error": f"执行POC时出错: {str(e)}"}

    def _execute_python_poc(self, poc_file_path: str, target_url: str) -> Dict:
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

            # 动态导入POC模块
            module_name = f"poc_module_{int(time.time() * 1000)}"
            spec = importlib.util.spec_from_file_location(module_name, poc_path)
            poc_module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = poc_module
            spec.loader.exec_module(poc_module)

            # 检查scan函数是否存在
            if not hasattr(poc_module, 'scan'):
                raise AttributeError("POC脚本中未找到scan函数")

            # 执行scan函数
            scan = poc_module.scan
            result = scan(normalized_url)

            # 清理模块（避免内存泄漏）
            if module_name in sys.modules:
                del sys.modules[module_name]

            # 验证返回格式
            if not isinstance(result, dict):
                result = {
                    "vulnerable": False,
                    "reason": "扫描函数返回格式不正确",
                    "details": str(result)
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

    def _normalize_url(self, url: str) -> str:
        """
        标准化URL格式

        Args:
            url: 原始URL

        Returns:
            str: 标准化后的URL（http(s)://host:port/）
        """
        # 如果没有协议，默认添加http://
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        # 解析URL
        parsed = urlparse(url)
        scheme = parsed.scheme
        netloc = parsed.netloc

        # 如果没有指定端口，使用默认端口
        if ':' not in netloc:
            if scheme == 'https':
                netloc = f"{netloc}:443"
            else:
                netloc = f"{netloc}:80"

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

            print(f"[OK] POC已删除: ID={poc_id}")
            return True

        except Exception as e:
            print(f"[X] 删除POC失败: {str(e)}")
            return False


# 创建全局实例
poc_library_service = PocLibraryService()