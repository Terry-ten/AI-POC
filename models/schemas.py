"""
数据模型定义
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class VulnerabilityRequest(BaseModel):
    """漏洞信息请求模型"""
    vulnerability_info: str = Field(..., description="漏洞信息，可以是描述、CVE编号、HTTP数据包等")
    target_info: Optional[str] = Field(None, description="目标系统信息（可选）")

    class Config:
        json_schema_extra = {
            "example": {
                "vulnerability_info": "目标网站存在SQL注入漏洞，位于登录页面的username参数",
                "target_info": "Web应用 - MySQL数据库 - http://example.com/login"
            }
        }


class PocResponse(BaseModel):
    """POC代码响应模型"""
    success: bool = Field(..., description="是否成功生成")
    vulnerability_type: Optional[str] = Field(None, description="识别出的Web漏洞类型")
    original_vulnerability_info: Optional[str] = Field(None, description="原始漏洞信息")
    poc_code: Optional[str] = Field(None, description="生成的POC验证代码（可验证时）")
    explanation: Optional[str] = Field(None, description="代码说明和使用方法")
    verifiable: bool = Field(True, description="是否可以单POC脚本自动化验证")
    manual_steps: Optional[Dict[str, Any]] = Field(None, description="人工操作指南（不可验证时）")
    error: Optional[str] = Field(None, description="错误信息")
    warning: str = Field(..., description="安全警告")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "vulnerability_type": "SQL注入",
                "original_vulnerability_info": "目标网站存在SQL注入漏洞，位于登录页面的username参数",
                "poc_code": "# POC验证代码\nimport requests\n...",
                "explanation": "该代码用于验证SQL注入漏洞是否存在，请在授权环境下使用",
                "verifiable": True,
                "manual_steps": None,
                "error": None,
                "warning": "⚠️ 仅用于授权测试"
            }
        }


class ScanRequest(BaseModel):
    """扫描请求模型"""
    target_url: str = Field(..., description="目标URL")

    class Config:
        json_schema_extra = {
            "example": {
                "target_url": "http://example.com"
            }
        }


class ScanResponse(BaseModel):
    """扫描结果响应模型"""
    success: bool = Field(..., description="扫描是否成功执行")
    target_url: str = Field(..., description="标准化后的目标URL")
    vulnerable: bool = Field(..., description="是否存在漏洞")
    reason: str = Field(..., description="判断依据")
    details: Optional[str] = Field(None, description="详细信息")
    error: Optional[str] = Field(None, description="错误信息")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "target_url": "http://example.com:80/",
                "vulnerable": True,
                "reason": "检测到SQL错误回显",
                "details": "在username参数注入单引号后，响应返回了MySQL错误信息",
                "error": None
            }
        }
