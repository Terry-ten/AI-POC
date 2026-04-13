"""
执行结果结构化分类器

第一阶段只做最小可扩展分类，不追求覆盖全部异常。
"""

import json
from typing import Any, Dict, Optional


NETWORK_CODES = (
    ("dns", ("name or service not known", "temporary failure in name resolution", "getaddrinfo failed", "nodename nor servname provided", "dns")),
    ("connect_timeout", ("connect timeout",)),
    ("read_timeout", ("read timed out", "read timeout")),
    ("connection_refused", ("connection refused",)),
    ("connection_reset", ("connection reset", "connection aborted")),
    ("connect_failed", ("failed to establish a new connection", "max retries exceeded", "newconnectionerror")),
    ("timeout", ("timed out", "timeout")),
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _build_classification(
    category: Optional[str],
    code: Optional[str],
    stage: Optional[str],
    retryable: bool = False,
) -> Dict[str, Any]:
    return {
        "failure_category": category,
        "failure_code": code,
        "failure_stage": stage,
        "retryable": bool(retryable),
    }


def classify_execution_outcome(outcome: Dict[str, Any]) -> Dict[str, Any]:
    """
    将单条执行结果转为最小结构化分类。

    outcome 兼容 execute_poc / batch 子任务的统一结构：
    {
        "success": bool,
        "error": str | None,
        "result": {
            "vulnerable": bool,
            "reason": str,
            "details": any
        }
    }
    """
    result = outcome.get("result") or {}
    vulnerable = bool(result.get("vulnerable"))
    success = bool(outcome.get("success"))
    error_text = _stringify(outcome.get("error"))
    reason_text = _stringify(result.get("reason"))
    details_text = _stringify(result.get("details"))
    combined = " ".join(part for part in (error_text, reason_text, details_text) if part).lower()

    if success and vulnerable:
        return _build_classification(None, None, None, retryable=False)

    if "oob 运行环境不可用" in combined or "interactsh" in combined or "ceye" in combined:
        if "未启用" in combined or "not configured" in combined:
            return _build_classification("oob_error", "not_configured", "precheck", retryable=False)
        return _build_classification("oob_error", "runtime_unavailable", "precheck", retryable=False)

    if "nuclei" in combined:
        if "不可用" in combined or "未安装" in combined:
            return _build_classification("nuclei_error", "engine_unavailable", "precheck", retryable=False)
        if "超时" in combined or "timeout" in combined:
            return _build_classification("nuclei_error", "scan_timeout", "engine_execution", retryable=True)
        if not success:
            return _build_classification("nuclei_error", "scan_failed", "engine_execution", retryable=False)

    if "syntaxerror" in combined or "invalid syntax" in combined or "unexpected character after line continuation character" in combined:
        return _build_classification("code_error", "syntax_error", "code_execution", retryable=False)

    if "缺少依赖" in combined or "missing_dependency" in combined:
        return _build_classification("environment_error", "missing_dependency", "precheck", retryable=False)

    if "modulenotfounderror" in combined or "no module named" in combined or "importerror" in combined:
        return _build_classification("environment_error", "import_error", "code_execution", retryable=False)

    for code, keywords in NETWORK_CODES:
        if any(keyword in combined for keyword in keywords):
            return _build_classification("network_error", code, "request_send", retryable=True)

    if not success:
        return _build_classification("unknown", "unclassified", "code_execution", retryable=False)

    return _build_classification("not_vulnerable", "no_evidence_found", "result_judgement", retryable=False)
