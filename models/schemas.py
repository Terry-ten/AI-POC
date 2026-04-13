"""
数据模型定义
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class VulnerabilityRequest(BaseModel):
    """漏洞信息请求模型"""
    vulnerability_info: str = Field(..., description="漏洞信息，可以是描述、CVE编号、HTTP数据包等")
    target_info: Optional[str] = Field(None, description="目标系统信息（可选，已废弃）")
    enable_second_review: bool = Field(False, description="是否启用二次大模型审核")

    class Config:
        json_schema_extra = {
            "example": {
                "vulnerability_info": "目标网站存在SQL注入漏洞，位于登录页面的username参数",
                "enable_second_review": False,
            }
        }


class PocResponse(BaseModel):
    """POC代码响应模型"""
    success: bool = Field(..., description="是否成功生成")
    vulnerability_name: Optional[str] = Field(None, description="漏洞名称，包含产品/框架信息")
    vulnerability_type: Optional[str] = Field(None, description="识别出的Web漏洞类型")
    original_vulnerability_info: Optional[str] = Field(None, description="原始漏洞信息")
    poc_code: Optional[str] = Field(None, description="生成的POC验证代码（可验证时）")
    explanation: Optional[str] = Field(None, description="代码说明和使用方法")
    verifiable: bool = Field(True, description="是否可以单POC脚本自动化验证")
    execution_mode: Optional[str] = Field(None, description="执行模式：url_only/url_with_params/manual_guide")
    verification_method: Optional[str] = Field(None, description="验证方式：direct/oob/manual")
    input_schema: Optional[List[Dict[str, Any]]] = Field(None, description="运行时输入定义，仅url_with_params时使用")
    manual_steps: Optional[Dict[str, Any]] = Field(None, description="人工操作指南（不可验证时）")
    review_enabled: bool = Field(False, description="是否启用了二次大模型审核")
    review_applied: bool = Field(False, description="二次审核结果是否已应用")
    review_model: Optional[str] = Field(None, description="二次审核所用模型")
    review_error: Optional[str] = Field(None, description="二次审核失败原因")
    dependency_check: Optional[Dict[str, Any]] = Field(None, description="生成结果的依赖预检信息")
    error: Optional[str] = Field(None, description="错误信息")
    warning: str = Field(..., description="安全警告")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "vulnerability_name": "ECShop 2.x/3.x SQL注入导致远程代码执行",
                "vulnerability_type": "SQL注入",
                "original_vulnerability_info": "目标网站存在SQL注入漏洞，位于登录页面的username参数",
                "poc_code": "# POC验证代码\nimport requests\n...",
                "explanation": "该代码用于验证SQL注入漏洞是否存在，请在授权环境下使用",
                "verifiable": True,
                "execution_mode": "url_only",
                "verification_method": "direct",
                "input_schema": None,
                "manual_steps": None,
                "review_enabled": False,
                "review_applied": False,
                "review_model": None,
                "review_error": None,
                "dependency_check": {
                    "ok": True,
                    "imports": ["requests"],
                    "missing": [],
                    "summary": "依赖检查通过"
                },
                "error": None,
                "warning": "⚠️ 仅用于授权测试"
            }
        }


class ScanRequest(BaseModel):
    """扫描请求模型"""
    target_url: str = Field(..., description="目标URL")
    runtime_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="运行时附加参数，仅 url_with_params 模式使用"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "target_url": "http://example.com",
                "runtime_params": {
                    "cookie": "PHPSESSID=demo"
                }
            }
        }


class LLMConfigRequest(BaseModel):
    """LLM配置更新请求模型"""
    api_key: str = Field(..., description="LLM API密钥")
    model_id: str = Field(..., description="模型ID，例如: gpt-4, claude-3-sonnet")
    base_url: str = Field(..., description="API基础URL，例如: https://api.openai.com/v1")
    temperature: Optional[float] = Field(0.1, description="温度参数（0-2），控制随机性")
    max_tokens: Optional[int] = Field(None, description="最大token数")

    class Config:
        json_schema_extra = {
            "example": {
                "api_key": "sk-xxxxxxxxxxxxx",
                "model_id": "gpt-4",
                "base_url": "https://api.openai.com/v1",
                "temperature": 0.7,
                "max_tokens": 4096
            }
        }


class LLMConfigResponse(BaseModel):
    """LLM配置响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    current_config: Dict[str, Any] = Field(..., description="当前配置（隐藏敏感信息）")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "LLM配置已更新",
                "current_config": {
                    "model_id": "gpt-4",
                    "base_url": "https://api.openai.com/v1",
                    "temperature": 0.7,
                    "api_key_preview": "sk-***...***xxx"
                }
            }
        }


class OOBConfigRequest(BaseModel):
    """OOB配置更新请求模型"""
    enabled: bool = Field(False, description="是否启用OOB验证")
    provider: str = Field("interactsh", description="OOB提供商：interactsh/ceye")
    interactsh_server: Optional[str] = Field("oast.me", description="Interactsh服务地址")
    interactsh_token: Optional[str] = Field(None, description="Interactsh鉴权Token")
    ceye_token: Optional[str] = Field(None, description="CEye Token")
    ceye_base_url: Optional[str] = Field("http://api.ceye.io/v1", description="CEye API地址")
    poll_interval: Optional[float] = Field(1.0, description="轮询间隔（秒）")
    max_polls: Optional[int] = Field(3, description="最大轮询次数")


class OOBConfigResponse(BaseModel):
    """OOB配置响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    current_config: Dict[str, Any] = Field(..., description="当前配置（隐藏敏感信息）")


class AssetSourceConfigRequest(BaseModel):
    """空间测绘配置更新请求"""
    provider: str = Field(..., description="平台：fofa/hunter/quake")
    email: Optional[str] = Field(None, description="FOFA 邮箱，仅 FOFA 使用")
    token: Optional[str] = Field(None, description="平台 Token")
    base_url: Optional[str] = Field(None, description="平台 API 地址")


class AssetSourceConfigResponse(BaseModel):
    """空间测绘配置响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    current_config: Dict[str, Any] = Field(..., description="当前配置（隐藏敏感信息）")


class AssetSourceImportRequest(BaseModel):
    """空间测绘目标导入请求"""
    provider: str = Field(..., description="平台：fofa/hunter/quake")
    query: str = Field(..., description="搜索语句")
    pages: int = Field(1, description="页数")


# ==================== Nuclei 扫描相关模型 ====================

class NucleiTemplate(BaseModel):
    """Nuclei 模板信息"""
    id: str = Field(..., description="模板ID")
    name: str = Field(..., description="模板名称")
    author: str = Field(..., description="作者")
    severity: str = Field(..., description="严重程度")
    description: str = Field("", description="描述")
    tags: List[str] = Field(default_factory=list, description="标签")
    file_path: str = Field(..., description="文件路径")
    relative_path: str = Field(..., description="相对路径")


class NucleiScanRequest(BaseModel):
    """Nuclei 扫描请求模型"""
    target_url: str = Field(..., description="目标URL")
    template_paths: Optional[List[str]] = Field(None, description="要使用的模板相对路径列表")
    folder: Optional[str] = Field(None, description="要扫描的文件夹")
    timeout: int = Field(120, description="扫描超时时间（秒）")

    class Config:
        json_schema_extra = {
            "example": {
                "target_url": "http://example.com",
                "template_paths": ["http/cves/CVE-2021-xxxxx.yaml"],
                "folder": "http/cves",
                "timeout": 120
            }
        }


class NucleiTaskCreateRequest(BaseModel):
    """Nuclei 任务化扫描请求模型"""
    target_urls: List[str] = Field(..., description="目标URL列表")
    template_paths: Optional[List[str]] = Field(None, description="要使用的模板相对路径列表")
    folder: Optional[str] = Field(None, description="要扫描的文件夹")
    concurrency: Optional[int] = Field(3, description="并发数，默认3")

    class Config:
        json_schema_extra = {
            "example": {
                "target_urls": ["http://example.com", "http://example.org"],
                "template_paths": ["http/cves/demo.yaml"],
                "folder": None,
                "concurrency": 3
            }
        }


class NucleiFinding(BaseModel):
    """Nuclei 扫描发现"""
    template_id: str = Field(..., description="模板ID")
    template_name: str = Field(..., description="模板名称")
    severity: str = Field(..., description="严重程度")
    type: str = Field("", description="漏洞类型")
    host: str = Field(..., description="目标主机")
    matched_at: str = Field("", description="匹配位置")
    matcher_name: str = Field("", description="匹配器名称")
    extracted_results: List[str] = Field(default_factory=list, description="提取结果")
    description: str = Field("", description="描述")
    tags: List[str] = Field(default_factory=list, description="标签")
    reference: List[str] = Field(default_factory=list, description="参考链接")
    curl_command: str = Field("", description="curl命令")
    timestamp: str = Field("", description="时间戳")


class NucleiScanResponse(BaseModel):
    """Nuclei 扫描响应模型"""
    success: bool = Field(..., description="是否成功")
    target_url: str = Field(..., description="目标URL")
    findings: List[Dict[str, Any]] = Field(default_factory=list, description="发现的漏洞列表")
    total_findings: int = Field(0, description="发现漏洞数量")
    vulnerable: bool = Field(False, description="是否存在漏洞")
    errors: Optional[List[str]] = Field(None, description="错误信息")
    warnings: Optional[List[str]] = Field(None, description="警告信息")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "target_url": "http://example.com",
                "findings": [],
                "total_findings": 0,
                "vulnerable": False,
                "errors": None,
                "warnings": None
            }
        }


class NucleiStatusResponse(BaseModel):
    """Nuclei 状态检查响应"""
    available: bool = Field(..., description="Nuclei是否可用")
    version: Optional[str] = Field(None, description="版本信息")
    path: Optional[str] = Field(None, description="可执行文件路径")
    error: Optional[str] = Field(None, description="错误信息")
    templates_count: int = Field(0, description="可用模板数量")


# ==================== 批量任务相关模型 ====================

class BatchTaskCreateRequest(BaseModel):
    """批量任务创建请求"""
    target_urls: List[str] = Field(..., description="目标URL列表")
    poc_ids: List[int] = Field(..., description="POC ID列表")
    concurrency: Optional[int] = Field(3, description="并发数，默认3")

    class Config:
        json_schema_extra = {
            "example": {
                "target_urls": ["http://example.com", "http://example.org"],
                "poc_ids": [101, 102, 103],
                "concurrency": 3
            }
        }


class BatchTaskActionResponse(BaseModel):
    """批量任务通用响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    task: Optional[Dict[str, Any]] = Field(None, description="任务信息")
