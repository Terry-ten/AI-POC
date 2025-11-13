"""
扫描服务 - 负责管理和执行扫描脚本
"""
import os
import re
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse, urlunparse
import logging
import hashlib
import time

# 配置日志
logger = logging.getLogger(__name__)

# 扫描脚本保存目录
SCAN_SCRIPTS_DIR = Path(__file__).parent.parent / "saved_scans"
SCAN_SCRIPTS_DIR.mkdir(exist_ok=True)

# 固定的文件名
SCAN_FILE_NAME = "scan.py"  # 最终的扫描文件
TEST_SCAN_FILE_NAME = "testscan.py"  # 测试扫描文件（初始生成）
PROMPT_FILE_NAME = "prompt.txt"  # 原始prompt文件
EVALUATE_FILE_NAME = "evaluate.txt"  # 评审意见文件


class ScannerService:
    """扫描脚本管理和执行服务"""

    def __init__(self):
        self.scripts_dir = SCAN_SCRIPTS_DIR
        self.scan_file_path = self.scripts_dir / SCAN_FILE_NAME
        self.test_scan_file_path = self.scripts_dir / TEST_SCAN_FILE_NAME
        self.prompt_file_path = self.scripts_dir / PROMPT_FILE_NAME
        self.evaluate_file_path = self.scripts_dir / EVALUATE_FILE_NAME

    def save_initial_poc(
        self,
        vulnerability_type: str,
        vulnerability_info: str,
        poc_code: str,
        explanation: str
    ) -> Dict[str, str]:
        """
        保存初始POC到 testscan.py 和 prompt.txt（第一步）

        Args:
            vulnerability_type: 漏洞类型
            vulnerability_info: 漏洞描述信息
            poc_code: 初始扫描函数代码
            explanation: 函数说明

        Returns:
            包含文件路径的字典
        """
        try:
            # 构建 prompt.txt 内容
            prompt_content = f"""# POC验证代码生成记录

## 漏洞类型
{vulnerability_type}

## 漏洞描述
{vulnerability_info}

## 生成的POC代码
```python
{poc_code}
```

## 逻辑介绍
{explanation}

生成时间：{time.strftime("%Y-%m-%d %H:%M:%S")}
"""

            # 保存 prompt.txt（覆盖模式）
            with open(self.prompt_file_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)

            # 构建 testscan.py 内容
            test_scan_content = f'''"""
测试扫描脚本 - {vulnerability_type}

漏洞描述：
{vulnerability_info}

函数说明：
{explanation}

生成时间：{time.strftime("%Y-%m-%d %H:%M:%S")}

注意：本脚本为初始生成版本，正在等待评审
函数签名：def scan(url: str) -> dict
"""

{poc_code}

# 用于测试的主函数
if __name__ == "__main__":
    # 测试URL（请替换为实际目标）
    test_url = "http://example.com:80/"

    print(f"开始扫描: {{test_url}}")
    result = scan(test_url)
    print(f"\\n扫描结果:")
    print(f"  存在漏洞: {{result.get('vulnerable', False)}}")
    print(f"  判断依据: {{result.get('reason', '未知')}}")
    if result.get('details'):
        print(f"  详细信息: {{result.get('details')}}")
'''

            # 保存 testscan.py（覆盖模式）
            with open(self.test_scan_file_path, 'w', encoding='utf-8') as f:
                f.write(test_scan_content)

            logger.info(f"✅ 初始POC已保存")
            logger.info(f"   prompt文件：{self.prompt_file_path}")
            logger.info(f"   测试文件：{self.test_scan_file_path}")

            return {
                "prompt_file": str(self.prompt_file_path),
                "test_scan_file": str(self.test_scan_file_path),
                "vulnerability_type": vulnerability_type
            }

        except Exception as e:
            logger.error(f"❌ 保存初始POC失败：{str(e)}")
            raise Exception(f"保存初始POC失败：{str(e)}")

    def save_evaluation(self, evaluation: str) -> str:
        """
        保存评审意见到 evaluate.txt（第二步）

        Args:
            evaluation: 评审意见

        Returns:
            evaluate文件路径
        """
        try:
            # 读取 prompt.txt 内容
            with open(self.prompt_file_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read()

            # 构建 evaluate.txt 内容 = prompt + 评审意见
            evaluate_content = f"""{prompt_content}

{'='*80}
# 代码评审意见

{evaluation}

评审时间：{time.strftime("%Y-%m-%d %H:%M:%S")}
"""

            # 保存 evaluate.txt（覆盖模式）
            with open(self.evaluate_file_path, 'w', encoding='utf-8') as f:
                f.write(evaluate_content)

            logger.info(f"✅ 评审意见已保存：{self.evaluate_file_path}")

            return str(self.evaluate_file_path)

        except Exception as e:
            logger.error(f"❌ 保存评审意见失败：{str(e)}")
            raise Exception(f"保存评审意见失败：{str(e)}")

    def get_evaluate_content(self) -> str:
        """
        读取 evaluate.txt 内容

        Returns:
            evaluate文件内容
        """
        try:
            with open(self.evaluate_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"❌ 读取评审文件失败：{str(e)}")
            raise Exception(f"读取评审文件失败：{str(e)}")

    def get_prompt_content(self) -> str:
        """
        读取 prompt.txt 内容

        Returns:
            prompt文件内容
        """
        try:
            with open(self.prompt_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"❌ 读取prompt文件失败：{str(e)}")
            raise Exception(f"读取prompt文件失败：{str(e)}")

    def save_scan_function(
        self,
        vulnerability_type: str,
        vulnerability_info: str,
        poc_code: str,
        explanation: str
    ) -> Dict[str, str]:
        """
        保存扫描函数到固定文件 scan.py（会覆盖旧文件）

        注意：保存的代码必须包含一个名为 'scan' 的函数

        Args:
            vulnerability_type: 漏洞类型
            vulnerability_info: 漏洞描述信��
            poc_code: 扫描函数代码（必须包含 def scan(url) 函数定义）
            explanation: 函数说明

        Returns:
            包含file_path的字典
        """
        try:
            # 构建完整的脚本内容（包含元数据）
            script_content = f'''"""
扫描脚本 - {vulnerability_type}

漏洞描述：
{vulnerability_info}

函数说明：
{explanation}

生成时间：{time.strftime("%Y-%m-%d %H:%M:%S")}

注意：本脚本必须包含一个名为 'scan' 的函数
函数签名：def scan(url: str) -> dict
"""

{poc_code}

# 用于测试的主函数
if __name__ == "__main__":
    # 测试URL（请替换为实际目标）
    test_url = "http://example.com:80/"

    print(f"开始扫描: {{test_url}}")
    result = scan(test_url)
    print(f"\\n扫描结果:")
    print(f"  存在漏洞: {{result.get('vulnerable', False)}}")
    print(f"  判断依据: {{result.get('reason', '未知')}}")
    if result.get('details'):
        print(f"  详细信息: {{result.get('details')}}")
'''

            # 保存到固定文件（覆盖模式）
            with open(self.scan_file_path, 'w', encoding='utf-8') as f:
                f.write(script_content)

            logger.info(f"✅ 扫描函数已保存到：{SCAN_FILE_NAME}")
            logger.info(f"   文件路径：{self.scan_file_path}")
            logger.info(f"   漏洞类型：{vulnerability_type}")

            return {
                "filename": SCAN_FILE_NAME,
                "file_path": str(self.scan_file_path),
                "vulnerability_type": vulnerability_type
            }

        except Exception as e:
            logger.error(f"❌ 保存扫描函数失败：{str(e)}")
            raise Exception(f"保存扫描函数失败：{str(e)}")

    def normalize_url(self, url: str) -> str:
        """
        标准化URL格式：http(s)://x.x.x.x:port/

        Args:
            url: 原始URL

        Returns:
            标准化后的URL
        """
        try:
            # 如果没有协议，默认添加http://
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url

            # 解析URL
            parsed = urlparse(url)

            # 确保有scheme和netloc
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("无效的URL格式")

            # 获取host和port
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

            logger.info(f"URL标准化：{url} -> {normalized_url}")
            return normalized_url

        except Exception as e:
            logger.error(f"❌ URL标准化失败：{str(e)}")
            raise ValueError(f"URL格式不正确：{str(e)}")

    def execute_scan(self, target_url: str) -> Dict[str, any]:
        """
        执行扫描：加载并运行固定的 scan.py 文件中的 scan 函数

        工作流程：
        1. 标准化目标URL
        2. 检查 scan.py 文件是否存在
        3. 动态导入 scan.py 模块
        4. 调用其中的 scan(url) 函数
        5. 返回扫描结果

        Args:
            target_url: 目标URL（将被自动标准化）

        Returns:
            扫描结果字典，包含success、result等字段
            result字段包含：vulnerable（bool）、reason（str）、details（str）
        """
        try:
            # 标准化URL
            normalized_url = self.normalize_url(target_url)

            # 检查扫描文件是否存在
            if not self.scan_file_path.exists():
                raise FileNotFoundError(f"扫描文件 {SCAN_FILE_NAME} 不存在")

            logger.info(f"🔍 开始执行漏洞扫描")
            logger.info(f"   脚本文件：{SCAN_FILE_NAME}")
            logger.info(f"   目标URL：{normalized_url}")
            logger.info(f"   扫描函数：scan(url)")

            # 动态导入扫描脚本模块
            # 使用时间戳确保每次都重新加载（避免缓存）
            module_name = f"scan_module_{int(time.time() * 1000)}"
            spec = importlib.util.spec_from_file_location(module_name, self.scan_file_path)
            scan_module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = scan_module
            spec.loader.exec_module(scan_module)

            # 检查是否存在scan函数（必须命名为scan）
            if not hasattr(scan_module, 'scan'):
                raise AttributeError(f"扫描脚本中未找到scan函数，请确保函数名为'scan'")

            # 获取scan函数并执行扫描
            scan = scan_module.scan
            logger.info(f"   正在调用 scan('{normalized_url}')...")
            result = scan(normalized_url)

            logger.info(f"✅ scan函数执行完成")
            logger.info(f"   结果：{result}")

            # 清理模块（避免内存泄漏）
            if module_name in sys.modules:
                del sys.modules[module_name]

            # 确保返回格式正确
            if not isinstance(result, dict):
                result = {
                    "vulnerable": False,
                    "reason": "扫描函数返回格式不正确",
                    "details": str(result)
                }

            # 确保必需字段存在
            if "vulnerable" not in result:
                result["vulnerable"] = False
            if "reason" not in result:
                result["reason"] = "未提供判断原因"

            return {
                "success": True,
                "target_url": normalized_url,
                "result": result
            }

        except Exception as e:
            logger.error(f"❌ 扫描执行失败：{type(e).__name__} - {str(e)}")
            return {
                "success": False,
                "target_url": target_url,
                "error": f"{type(e).__name__}: {str(e)}",
                "result": {
                    "vulnerable": False,
                    "reason": f"扫描失败：{str(e)}",
                    "details": ""
                }
            }

    def has_scan_file(self) -> bool:
        """
        检查是否存在扫描文件

        Returns:
            True表示存在，False表示不存在
        """
        return self.scan_file_path.exists()

    def get_scan_file_info(self) -> Optional[Dict[str, str]]:
        """
        获取当前扫描文件的信息

        Returns:
            文件信息字典，如果文件不存在则返回None
        """
        if not self.has_scan_file():
            return None

        try:
            stat = self.scan_file_path.stat()
            return {
                "filename": SCAN_FILE_NAME,
                "file_path": str(self.scan_file_path),
                "created_time": time.ctime(stat.st_ctime),
                "modified_time": time.ctime(stat.st_mtime),
                "size": f"{stat.st_size} bytes"
            }
        except Exception as e:
            logger.error(f"获取文件信息失败：{str(e)}")
            return None


# 创建全局服务实例
scanner_service = ScannerService()