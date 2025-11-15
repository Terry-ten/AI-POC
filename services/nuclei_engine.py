"""
Nuclei执行引擎

功能：
1. 执行Nuclei模板进行漏洞扫描
2. 验证Nuclei模板格式
3. 解析Nuclei扫描结果
"""

import subprocess
import json
import yaml
import hashlib
import shutil
from pathlib import Path
from typing import Dict, Optional


class NucleiEngine:
    def __init__(self, nuclei_path: str = "nuclei"):
        """
        初始化Nuclei引擎

        Args:
            nuclei_path: nuclei可执行文件路径（默认从PATH中查找）
        """
        self.nuclei_path = nuclei_path
        self.is_available = self.check_nuclei_installed()

    def check_nuclei_installed(self) -> bool:
        """
        检查Nuclei是否安装

        Returns:
            bool: 是否已安装
        """
        try:
            result = subprocess.run(
                [self.nuclei_path, '-version'],
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode == 0:
                version_info = result.stdout.strip()
                print(f"[OK] Nuclei已安装: {version_info}")
                return True
            else:
                print("[X] Nuclei未正确安装")
                return False
        except FileNotFoundError:
            print(f"[X] Nuclei未找到，请确保已安装并添加到PATH中")
            print("  安装方法: https://github.com/projectdiscovery/nuclei#install-nuclei")
            return False
        except Exception as e:
            print(f"[X] 检查Nuclei时出错: {str(e)}")
            return False

    def execute(self, template_path: str, target_url: str, timeout: int = 30) -> Dict:
        """
        执行Nuclei扫描

        Args:
            template_path: Nuclei模板文件路径
            target_url: 目标URL
            timeout: 超时时间（秒）

        Returns:
            Dict: 扫描结果
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Nuclei未安装或不可用"
            }

        try:
            # 检查模板文件是否存在
            if not Path(template_path).exists():
                return {
                    "success": False,
                    "error": f"模板文件不存在: {template_path}"
                }

            # 执行nuclei命令
            result = subprocess.run(
                [
                    self.nuclei_path,
                    '-t', template_path,
                    '-u', target_url,
                    '-json',
                    '-silent',
                    '-no-color'
                ],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # 解析输出
            if result.stdout:
                # Nuclei以JSON Lines格式输出结果（每行一个JSON对象）
                nuclei_results = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            nuclei_results.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

                if nuclei_results:
                    # 发现漏洞
                    first_result = nuclei_results[0]
                    template_info = first_result.get('info', {})

                    return {
                        "success": True,
                        "target_url": target_url,
                        "result": {
                            "vulnerable": True,
                            "reason": f"Nuclei检测到漏洞: {template_info.get('name', 'Unknown')}",
                            "details": {
                                "template_id": first_result.get('template-id', first_result.get('templateID')),
                                "template_name": template_info.get('name'),
                                "severity": template_info.get('severity'),
                                "matched_at": first_result.get('matched-at', first_result.get('matched')),
                                "matcher_name": first_result.get('matcher-name', first_result.get('matcher_name')),
                                "extractor": first_result.get('extracted-results'),
                                "curl_command": first_result.get('curl-command'),
                                "raw_output": nuclei_results
                            }
                        }
                    }
                else:
                    # 未发现漏洞
                    return {
                        "success": True,
                        "target_url": target_url,
                        "result": {
                            "vulnerable": False,
                            "reason": "Nuclei未检测到漏洞",
                            "details": {}
                        }
                    }
            else:
                # 无输出，表示未发现漏洞
                return {
                    "success": True,
                    "target_url": target_url,
                    "result": {
                        "vulnerable": False,
                        "reason": "扫描完成，未发现漏洞",
                        "details": {}
                    }
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Nuclei执行超时（{timeout}秒）"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Nuclei执行失败: {type(e).__name__}: {str(e)}"
            }

    def validate_template(self, template_path: str) -> Dict:
        """
        验证Nuclei模板格式

        Args:
            template_path: 模板文件路径

        Returns:
            Dict: 验证结果 {"valid": bool, "error": str}
        """
        if not self.is_available:
            return {"valid": False, "error": "Nuclei未安装或不可用"}

        try:
            # 使用nuclei的-validate选项验证模板
            result = subprocess.run(
                [self.nuclei_path, '-t', template_path, '-validate'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return {"valid": True, "error": None}
            else:
                return {
                    "valid": False,
                    "error": result.stderr.strip() or "模板格式验证失败"
                }

        except subprocess.TimeoutExpired:
            return {"valid": False, "error": "验证超时"}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def parse_template_info(self, template_path: str) -> Optional[Dict]:
        """
        解析Nuclei模板信息

        Args:
            template_path: 模板文件路径

        Returns:
            Dict: 模板信息，如果解析失败返回None
        """
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)

            if not template_data:
                return None

            info = template_data.get('info', {})

            return {
                "id": template_data.get('id', ''),
                "name": info.get('name', 'Unknown'),
                "author": info.get('author', ''),
                "severity": info.get('severity', 'unknown'),
                "description": info.get('description', ''),
                "reference": info.get('reference', []),
                "tags": info.get('tags', []),
                "classification": info.get('classification', {}),
                "metadata": info.get('metadata', {})
            }

        except Exception as e:
            print(f"[X] 解析模板信息失败: {str(e)}")
            return None

    def import_template(self, source_template_path: str, dest_dir: Path) -> Dict:
        """
        导入Nuclei模板到POC库

        Args:
            source_template_path: 源模板文件路径
            dest_dir: 目标目录

        Returns:
            Dict: {"success": bool, "template_path": str, "info": dict, "error": str}
        """
        try:
            # 验证模板
            validation = self.validate_template(source_template_path)
            if not validation['valid']:
                return {
                    "success": False,
                    "error": f"模板验证失败: {validation['error']}"
                }

            # 解析模板信息
            template_info = self.parse_template_info(source_template_path)
            if not template_info:
                return {
                    "success": False,
                    "error": "无法解析模板信息"
                }

            # 生成目标文件名
            template_id = template_info['id'] or hashlib.md5(
                template_info['name'].encode()
            ).hexdigest()[:8]

            dest_file = dest_dir / f"{template_id}.yaml"

            # 如果文件已存在，添加时间戳后缀
            if dest_file.exists():
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_file = dest_dir / f"{template_id}_{timestamp}.yaml"

            # 复制模板文件
            shutil.copy(source_template_path, dest_file)

            return {
                "success": True,
                "template_path": str(dest_file),
                "info": template_info,
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"导入模板失败: {str(e)}"
            }


# 创建全局实例
nuclei_engine = NucleiEngine()