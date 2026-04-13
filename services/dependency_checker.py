"""
Python POC 依赖预检

只做最小能力：
1. 从源码中提取 import
2. 判断模块是否属于标准库、平台内置 helper、或当前环境已安装
3. 给出缺失依赖列表
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Set


PLATFORM_PROVIDED_MODULES = {
    "http_runtime",
    "oob_runtime",
}


def _get_stdlib_modules() -> Set[str]:
    names = getattr(sys, "stdlib_module_names", None)
    if names:
        return set(names)
    return set()


def _extract_import_roots(code: str) -> List[str]:
    tree = ast.parse(code)
    modules: Set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root:
                    modules.add(root)
        elif isinstance(node, ast.ImportFrom):
            if node.level and not node.module:
                continue
            if node.module:
                root = node.module.split(".", 1)[0]
                if root:
                    modules.add(root)

    return sorted(modules)


def _is_module_available(module_name: str) -> bool:
    if module_name in PLATFORM_PROVIDED_MODULES:
        return True
    if module_name in _get_stdlib_modules():
        return True
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def check_python_code_dependencies(code: str) -> Dict[str, Any]:
    try:
        imports = _extract_import_roots(code)
    except SyntaxError as exc:
        return {
            "ok": False,
            "imports": [],
            "missing": [],
            "summary": "代码无法解析，已跳过依赖预检",
            "parse_error": f"{type(exc).__name__}: {exc}",
        }

    missing = [name for name in imports if not _is_module_available(name)]
    return {
        "ok": len(missing) == 0,
        "imports": imports,
        "missing": missing,
        "summary": "依赖检查通过" if not missing else f"缺少依赖: {', '.join(missing)}",
    }


def check_python_file_dependencies(file_path: str | Path) -> Dict[str, Any]:
    code = Path(file_path).read_text(encoding="utf-8")
    return check_python_code_dependencies(code)
