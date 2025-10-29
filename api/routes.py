"""
API路由定义
"""
from fastapi import APIRouter, HTTPException, status
from models.schemas import VulnerabilityRequest, PocResponse
from services.llm_service import llm_service
from config import settings

router = APIRouter()


@router.post(
    "/generate-poc",
    response_model=PocResponse,
    summary="生成Web漏洞POC代码",
    description="根据漏洞信息生成对应的Web漏洞POC验证代码",
)
async def generate_poc(request: VulnerabilityRequest) -> PocResponse:
    """
    接收Web漏洞信息，调用大模型生成POC验证代码

    - **vulnerability_info**: 漏洞信息，可以是描述、CVE编号、HTTP数据包等
    - **target_info**: 目标系统信息（可选）
    """
    try:
        # 调用LLM服务生成POC代码
        result = await llm_service.generate_poc_code(
            vulnerability_info=request.vulnerability_info,
            target_info=request.target_info,
        )

        return PocResponse(
            success=True,
            vulnerability_type=result.get("vulnerability_type"),
            original_vulnerability_info=result.get("original_vulnerability_info"),
            poc_code=result.get("poc_code"),
            explanation=result.get("explanation"),
            error=None,
            warning=settings.SECURITY_WARNING,
        )

    except Exception as e:
        return PocResponse(
            success=False,
            vulnerability_type=None,
            original_vulnerability_info=request.vulnerability_info,
            poc_code=None,
            explanation=None,
            error=str(e),
            warning=settings.SECURITY_WARNING,
        )


@router.get("/health", summary="健康检查")
async def health_check():
    """API健康检查端点"""
    return {
        "status": "healthy",
        "service": "Vulnerability to POC Generator",
        "version": "1.0.0",
    }
