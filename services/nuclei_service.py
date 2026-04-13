"""
Nuclei 漏洞扫描引擎服务
负责管理和执行 Nuclei YAML 模板扫描
"""
import subprocess
import json
import yaml
import logging
import asyncio
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Optional, Generator, Tuple, AsyncGenerator
from functools import lru_cache
import os
import time

logger = logging.getLogger(__name__)

# 全局线程池
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
PROCESS_TIMEOUT_BUFFER = 30


class NucleiService:
    """Nuclei 漏洞扫描服务"""

    def __init__(self):
        # 项目根目录
        self.project_root = Path(__file__).parent.parent
        # Nuclei 可执行文件路径
        self.nuclei_path = self.project_root / "nuclei.exe"
        # YAML 模板目录
        self.templates_dir = self.project_root / "pocs" / "nuclei"

        # 确保模板目录存在
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # 缓存
        self._folder_cache = None
        self._folder_cache_time = 0
        self._templates_cache = {}
        self._templates_cache_time = 0
        self._cache_ttl = 300  # 缓存5分钟

    def check_nuclei_available(self) -> Dict:
        """检查 Nuclei 是否可用"""
        try:
            if not self.nuclei_path.exists():
                return {
                    "available": False,
                    "error": f"Nuclei 可执行文件不存在: {self.nuclei_path}"
                }

            # 尝试执行 nuclei -version
            result = subprocess.run(
                [str(self.nuclei_path), "-version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            version_info = result.stdout.strip() or result.stderr.strip()

            return {
                "available": True,
                "version": version_info,
                "path": str(self.nuclei_path)
            }
        except subprocess.TimeoutExpired:
            return {"available": False, "error": "Nuclei 执行超时"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def get_folder_structure(self) -> List[Dict]:
        """获取模板文件夹结构（带缓存）"""
        current_time = time.time()

        # 检查缓存是否有效
        if self._folder_cache and (current_time - self._folder_cache_time) < self._cache_ttl:
            return self._folder_cache

        folders = []
        if not self.templates_dir.exists():
            return folders

        # 统计根目录的模板
        root_count = len(list(self.templates_dir.glob("*.yaml"))) + len(list(self.templates_dir.glob("*.yml")))
        if root_count > 0:
            folders.append({
                "path": "",
                "name": "根目录",
                "count": root_count
            })

        # 遍历子目录
        for item in sorted(self.templates_dir.iterdir()):
            if item.is_dir() and not item.name.startswith('.'):
                yaml_count = len(list(item.rglob("*.yaml"))) + len(list(item.rglob("*.yml")))
                if yaml_count > 0:
                    folders.append({
                        "path": item.name,
                        "name": item.name,
                        "count": yaml_count
                    })

        # 更新缓存
        self._folder_cache = folders
        self._folder_cache_time = current_time

        return folders

    def get_templates_by_folder(self, folder: str = "", page: int = 1, page_size: int = 100,
                                 keyword: str = "") -> Tuple[List[Dict], int]:
        """
        分页获取指定文件夹的模板

        Args:
            folder: 文件夹路径（相对于templates_dir）
            page: 页码，从1开始
            page_size: 每页数量
            keyword: 搜索关键词

        Returns:
            (模板列表, 总数量)
        """
        cache_key = f"{folder}:{keyword}"
        current_time = time.time()

        # 检查缓存
        if cache_key in self._templates_cache:
            cached_data, cache_time = self._templates_cache[cache_key]
            if (current_time - cache_time) < self._cache_ttl:
                total = len(cached_data)
                start = (page - 1) * page_size
                end = start + page_size
                return cached_data[start:end], total

        # 确定搜索目录
        if folder:
            search_dir = self.templates_dir / folder
        else:
            search_dir = self.templates_dir

        if not search_dir.exists():
            return [], 0

        # 收集所有模板（只解析基本信息，不读取完整内容）
        templates = []

        # 根据是否有子目录决定搜索方式
        if folder:
            yaml_files = list(search_dir.rglob("*.yaml")) + list(search_dir.rglob("*.yml"))
        else:
            # 根目录只搜索当前层级
            yaml_files = list(search_dir.glob("*.yaml")) + list(search_dir.glob("*.yml"))

        for yaml_file in yaml_files:
            try:
                template_info = self._parse_template_fast(yaml_file)
                if template_info:
                    # 关键词过滤
                    if keyword:
                        keyword_lower = keyword.lower()
                        if not (keyword_lower in template_info["id"].lower() or
                                keyword_lower in template_info["name"].lower() or
                                keyword_lower in template_info.get("severity", "").lower()):
                            continue
                    templates.append(template_info)
            except Exception as e:
                logger.warning(f"解析模板失败 {yaml_file}: {e}")
                continue

        # 按严重程度排序
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "unknown": 5}
        templates.sort(key=lambda x: (severity_order.get(x.get("severity", "unknown"), 5), x.get("id", "")))

        # 更新缓存
        self._templates_cache[cache_key] = (templates, current_time)

        # 分页返回
        total = len(templates)
        start = (page - 1) * page_size
        end = start + page_size

        return templates[start:end], total

    def _parse_template_fast(self, yaml_path: Path) -> Optional[Dict]:
        """快速解析模板文件（只读取前几行获取基本信息）"""
        try:
            # 只读取文件前2KB来快速解析
            with open(yaml_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(2048)

            # 简单解析 id 和 info 块
            lines = content.split('\n')
            template_id = None
            name = None
            severity = "unknown"
            author = "unknown"
            description = ""

            in_info = False
            for line in lines:
                stripped = line.strip()

                if stripped.startswith('id:'):
                    template_id = stripped.split(':', 1)[1].strip().strip('"\'')
                elif stripped == 'info:':
                    in_info = True
                elif in_info:
                    if stripped.startswith('name:'):
                        name = stripped.split(':', 1)[1].strip().strip('"\'')
                    elif stripped.startswith('severity:'):
                        severity = stripped.split(':', 1)[1].strip().strip('"\'').lower()
                    elif stripped.startswith('author:'):
                        author = stripped.split(':', 1)[1].strip().strip('"\'')
                    elif stripped.startswith('description:'):
                        desc_part = stripped.split(':', 1)[1].strip()
                        if desc_part and not desc_part.startswith('|'):
                            description = desc_part.strip('"\'')
                    elif not line.startswith(' ') and not line.startswith('\t') and stripped:
                        # 退出 info 块
                        break

            if not template_id:
                template_id = yaml_path.stem

            if not name:
                name = template_id

            # 计算相对路径（统一使用正斜杠）
            try:
                relative_path = str(yaml_path.relative_to(self.templates_dir)).replace('\\', '/')
            except ValueError:
                relative_path = yaml_path.name

            return {
                "id": template_id,
                "name": name,
                "author": author,
                "severity": severity,
                "description": description[:200] if description else "",
                "file_path": str(yaml_path),
                "relative_path": relative_path
            }
        except Exception as e:
            logger.error(f"快速解析模板文件失败 {yaml_path}: {e}")
            return None

    def get_template_content(self, template_path: str) -> Optional[str]:
        """获取模板文件完整内容"""
        try:
            # template_path 是相对路径
            full_path = self.templates_dir / template_path
            if not full_path.exists():
                return None

            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取模板文件失败: {e}")
            return None

    def get_total_template_count(self) -> int:
        """获取模板总数"""
        if not self.templates_dir.exists():
            return 0
        return len(list(self.templates_dir.rglob("*.yaml"))) + len(list(self.templates_dir.rglob("*.yml")))

    def scan_single(self, target_url: str, template_path: str, timeout: int = 60) -> Dict:
        """使用单个模板扫描目标"""
        # 使用 Path 处理路径
        full_path = self.templates_dir / Path(template_path)
        if not full_path.exists():
            return {
                "success": False,
                "error": f"模板不存在: {template_path}"
            }
        return self._execute_scan(target_url, [str(full_path)], timeout)

    def scan_multiple(self, target_url: str, template_paths: List[str], timeout: int = 120) -> Dict:
        """使用多个模板扫描目标"""
        full_paths = []
        missing = []

        for path in template_paths:
            # 使用 Path 处理路径
            full_path = self.templates_dir / Path(path)
            if full_path.exists():
                full_paths.append(str(full_path))
            else:
                missing.append(path)

        if not full_paths:
            return {
                "success": False,
                "error": f"所有指定的模板都不存在"
            }

        result = self._execute_scan(target_url, full_paths, timeout)

        if missing:
            result["warnings"] = [f"以下模板不存在: {', '.join(missing)}"]

        return result

    def scan_folder(self, target_url: str, folder: str, timeout: int = 300) -> Dict:
        """扫描整个文件夹的模板"""
        if folder:
            scan_path = self.templates_dir / folder
        else:
            scan_path = self.templates_dir

        if not scan_path.exists():
            return {
                "success": False,
                "error": f"文件夹不存在: {folder}"
            }

        return self._execute_scan(target_url, [str(scan_path)], timeout)

    def _execute_scan(self, target_url: str, template_paths: List[str], timeout: int) -> Dict:
        """执行 Nuclei 扫描"""
        check_result = self.check_nuclei_available()
        if not check_result.get("available"):
            return {
                "success": False,
                "error": check_result.get("error", "Nuclei 不可用")
            }

        try:
            cmd = [
                str(self.nuclei_path),
                "-u", target_url,
                "-jsonl",
                "-silent",
                "-no-color",
                "-timeout", str(timeout)
            ]

            for path in template_paths:
                cmd.extend(["-t", path])

            logger.info(f"执行 Nuclei 扫描: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + PROCESS_TIMEOUT_BUFFER,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            findings = []
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            finding = json.loads(line)
                            findings.append(self._format_finding(finding))
                        except json.JSONDecodeError:
                            logger.warning(f"无法解析 JSON 行: {line}")

            errors = []
            if result.stderr:
                for line in result.stderr.strip().split('\n'):
                    if line and not line.startswith('[INF]') and not line.startswith('[WRN]'):
                        errors.append(line)

            return {
                "success": True,
                "target_url": target_url,
                "findings": findings,
                "total_findings": len(findings),
                "vulnerable": len(findings) > 0,
                "errors": errors if errors else None
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"扫描超时（{timeout}秒）"
            }
        except Exception as e:
            logger.error(f"Nuclei 扫描执行失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _format_finding(self, finding: Dict) -> Dict:
        """格式化扫描发现"""
        return {
            "template_id": finding.get("template-id", ""),
            "template_name": finding.get("info", {}).get("name", ""),
            "severity": finding.get("info", {}).get("severity", "unknown"),
            "type": finding.get("type", ""),
            "host": finding.get("host", ""),
            "matched_at": finding.get("matched-at", ""),
            "matcher_name": finding.get("matcher-name", ""),
            "extracted_results": finding.get("extracted-results", []),
            "description": finding.get("info", {}).get("description", ""),
            "tags": finding.get("info", {}).get("tags", []),
            "reference": finding.get("info", {}).get("reference", []),
            "curl_command": finding.get("curl-command", ""),
            "timestamp": finding.get("timestamp", "")
        }

    async def scan_stream_async(self, target_url: str, template_paths: List[str] = None,
                    folder: str = None, timeout: int = 120) -> AsyncGenerator[Dict, None]:
        """异步流式扫描"""
        check_result = self.check_nuclei_available()
        if not check_result.get("available"):
            yield {
                "type": "error",
                "message": check_result.get("error", "Nuclei 不可用")
            }
            return

        # 确定扫描路径
        paths = []
        missing_paths = []

        if template_paths:
            for p in template_paths:
                full_path = self.templates_dir / Path(p)
                logger.info(f"检查模板路径: {p} -> {full_path}")
                if full_path.exists():
                    paths.append(str(full_path))
                else:
                    missing_paths.append(p)
                    logger.warning(f"模板不存在: {full_path}")
        elif folder is not None:
            if folder:
                paths = [str(self.templates_dir / folder)]
            else:
                paths = [str(self.templates_dir)]
        else:
            paths = [str(self.templates_dir)]

        if not paths:
            yield {
                "type": "error",
                "message": f"没有找到可用的模板。缺失: {', '.join(missing_paths)}" if missing_paths else "没有找到可用的模板"
            }
            return

        cmd = [
            str(self.nuclei_path),
            "-u", target_url,
            "-jsonl",
            "-silent",
            "-no-color",
            "-timeout", str(timeout)
        ]

        for path in paths:
            cmd.extend(["-t", path])

        yield {
            "type": "status",
            "message": "开始扫描...",
            "target_url": target_url
        }

        logger.info(f"执行扫描命令: {' '.join(cmd)}")

        # 在线程池中执行同步的 subprocess
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                _executor,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout + PROCESS_TIMEOUT_BUFFER,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
            )

            findings = []
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if line:
                        try:
                            finding = json.loads(line)
                            formatted = self._format_finding(finding)
                            findings.append(formatted)
                            yield {
                                "type": "finding",
                                "data": formatted
                            }
                        except json.JSONDecodeError:
                            logger.debug(f"非JSON输出: {line}")

            yield {
                "type": "complete",
                "total_findings": len(findings),
                "vulnerable": len(findings) > 0
            }

        except subprocess.TimeoutExpired:
            yield {
                "type": "error",
                "message": f"扫描超时（{timeout}秒）"
            }
        except Exception as e:
            logger.error(f"扫描异常: {e}")
            yield {
                "type": "error",
                "message": str(e)
            }

    def scan_stream(self, target_url: str, template_paths: List[str] = None,
                    folder: str = None, timeout: int = 120) -> Generator[Dict, None, None]:
        """流式扫描（同步版本，已废弃，请使用 scan_stream_async）"""
        check_result = self.check_nuclei_available()
        if not check_result.get("available"):
            yield {
                "type": "error",
                "message": check_result.get("error", "Nuclei 不可用")
            }
            return

        # 确定扫描路径
        paths = []
        missing_paths = []

        if template_paths:
            for p in template_paths:
                # 使用 Path 处理路径，自动适配系统分隔符
                full_path = self.templates_dir / Path(p)
                logger.info(f"检查模板路径: {p} -> {full_path}")
                if full_path.exists():
                    paths.append(str(full_path))
                else:
                    missing_paths.append(p)
                    logger.warning(f"模板不存在: {full_path}")
        elif folder is not None:
            if folder:
                paths = [str(self.templates_dir / folder)]
            else:
                paths = [str(self.templates_dir)]
        else:
            paths = [str(self.templates_dir)]

        if not paths:
            yield {
                "type": "error",
                "message": f"没有找到可用的模板。缺失: {', '.join(missing_paths)}" if missing_paths else "没有找到可用的模板"
            }
            return

        cmd = [
            str(self.nuclei_path),
            "-u", target_url,
            "-jsonl",
            "-silent",
            "-no-color",
            "-timeout", str(timeout)
        ]

        for path in paths:
            cmd.extend(["-t", path])

        yield {
            "type": "status",
            "message": "开始扫描...",
            "target_url": target_url
        }

        logger.info(f"执行流式扫描命令: {' '.join(cmd)}")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # 行缓冲
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            findings = []

            # 使用 communicate 并设置超时，而不是逐行读取
            try:
                stdout, stderr = process.communicate(timeout=timeout + PROCESS_TIMEOUT_BUFFER)

                # 处理输出
                if stdout:
                    for line in stdout.strip().split('\n'):
                        line = line.strip()
                        if line:
                            try:
                                finding = json.loads(line)
                                formatted = self._format_finding(finding)
                                findings.append(formatted)
                                yield {
                                    "type": "finding",
                                    "data": formatted
                                }
                            except json.JSONDecodeError:
                                logger.debug(f"非JSON输出: {line}")

                yield {
                    "type": "complete",
                    "total_findings": len(findings),
                    "vulnerable": len(findings) > 0
                }

            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()  # 清理
                yield {
                    "type": "error",
                    "message": f"扫描超时（{timeout}秒）"
                }

        except Exception as e:
            logger.error(f"流式扫描异常: {e}")
            yield {
                "type": "error",
                "message": str(e)
            }

    def clear_cache(self):
        """清除缓存"""
        self._folder_cache = None
        self._folder_cache_time = 0
        self._templates_cache = {}
        self._templates_cache_time = 0


# 创建单例实例
nuclei_service = NucleiService()
