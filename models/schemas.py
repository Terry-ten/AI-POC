"""
数据模型定义
"""
from pydantic import BaseModel, Field
from typing import Optional


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
    poc_code: Optional[str] = Field(None, description="生成的POC验证代码")
    explanation: Optional[str] = Field(None, description="代码说明和使用方法")
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
                "error": None,
                "warning": "⚠️ 仅用于授权测试"
            }
        }
