"""
API路由定义
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from models.schemas import VulnerabilityRequest, PocResponse, ScanRequest
from services.llm_service import llm_service
from services.poc_library_service import poc_library_service
from config import settings
import logging
import json
import asyncio
from pathlib import Path

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/generate-poc",
    summary="生成Web漏洞POC代码",
    description="使用GLM-4.6生成POC代码（支持实时进度反馈）",
)
async def generate_poc(request: VulnerabilityRequest):
    """
    接收Web漏洞信息，生成POC代码（流式响应）

    流程：
    1. 使用 GLM-4.6 生成POC，保存到 POC库

    - **vulnerability_info**: 漏洞信息，可以是描述、CVE编号、HTTP数据包等
    - **target_info**: 目标系统信息（可选）
    """

    async def generate_stream():
        try:
            logger.info("="*80)
            logger.info("开始POC生成流程")
            logger.info("="*80)

            # 发送开始消息
            yield f"data: {json.dumps({'type': 'status', 'step': 0, 'message': '开始生成流程...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            # 使用 GLM-4.6 生成POC
            yield f"data: {json.dumps({'type': 'status', 'step': 1, 'message': '正在使用 GLM-4.6 生成POC代码...'}, ensure_ascii=False)}\n\n"
            logger.info("使用 GLM-4.6 生成POC...")

            result = await llm_service.generate_initial_poc(
                vulnerability_info=request.vulnerability_info,
                target_info=request.target_info,
            )

            verifiable = result.get("verifiable", True)

            # 保存到POC库
            try:
                poc_id = poc_library_service.save_poc(
                    vuln_type=result.get("vulnerability_type") or "unknown",
                    vuln_info=result.get("original_vulnerability_info") or request.vulnerability_info,
                    poc_code=result.get("poc_code"),
                    explanation=result.get("explanation") or "",
                    poc_type="python" if verifiable else "manual",
                    tags=["auto-generated", "llm"],
                    metadata={"target_info": request.target_info},
                    verifiable=verifiable,
                    manual_steps=result.get("manual_steps")
                )
                logger.info(f"✅ {'可验证POC' if verifiable else '人工操作指南'}已保存到库，ID: {poc_id}")
            except Exception as e:
                logger.warning(f"⚠ 保存到POC库失败：{str(e)}")

            yield f"data: {json.dumps({'type': 'status', 'step': 1, 'message': '✅ POC已生成并保存到库'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            logger.info("="*80)
            logger.info("POC生成流程完成")
            logger.info("="*80)

            # 发送最终结果
            poc_response = PocResponse(
                success=True,
                vulnerability_type=result.get("vulnerability_type"),
                original_vulnerability_info=result.get("original_vulnerability_info"),
                poc_code=result.get("poc_code"),
                explanation=result.get("explanation"),
                verifiable=result.get("verifiable", True),
                manual_steps=result.get("manual_steps"),
                error=None,
                warning=settings.SECURITY_WARNING,
            )
            yield f"data: {json.dumps({'type': 'result', 'data': poc_response.model_dump()}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"❌ POC生成流程失败：{str(e)}")
            error_result = PocResponse(
                success=False,
                vulnerability_type=None,
                original_vulnerability_info=request.vulnerability_info,
                poc_code=None,
                explanation=None,
                error=str(e),
                warning=settings.SECURITY_WARNING,
            )
            yield f"data: {json.dumps({'type': 'error', 'data': error_result.model_dump()}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/health", summary="健康检查")
async def health_check():
    """API健康检查端点"""
    return {
        "status": "healthy",
        "service": "Vulnerability to POC Generator",
        "version": "1.0.0",
    }


# ==================== POC库管理API ====================

@router.get("/pocs/search", summary="搜索POC库")
async def search_pocs(
    vuln_type: str = None,
    poc_type: str = None,
    keyword: str = None,
    verifiable: bool = None,
    limit: int = 50,
    offset: int = 0
):
    """
    搜索POC库

    - **vuln_type**: 漏洞类型过滤（如: sqli, xss, rce）
    - **poc_type**: POC类型过滤（python/nuclei/manual）
    - **keyword**: 关键词搜索
    - **verifiable**: 是否可验证过滤（true=可验证, false=不可验证, null=全部）
    - **limit**: 返回数量限制
    - **offset**: 偏移量
    """
    try:
        pocs = poc_library_service.search_pocs(
            vuln_type=vuln_type,
            poc_type=poc_type,
            keyword=keyword,
            verifiable=verifiable,
            limit=limit,
            offset=offset
        )
        return {"success": True, "total": len(pocs), "pocs": pocs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pocs/{poc_id}", summary="获取POC详情")
async def get_poc(poc_id: int):
    """获取指定POC的详细信息"""
    poc = poc_library_service.get_poc_by_id(poc_id)
    if not poc:
        raise HTTPException(status_code=404, detail="POC不存在")
    return {"success": True, "poc": poc}


@router.post("/pocs/{poc_id}/execute", summary="执行指定POC")
async def execute_poc_by_id(poc_id: int, request: ScanRequest):
    """
    根据POC ID执行扫描

    - **poc_id**: POC记录ID
    - **target_url**: 目标URL
    """
    try:
        result = poc_library_service.execute_poc(poc_id, request.target_url)

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "执行失败")
            }

        return {
            "success": True,
            "poc_id": poc_id,
            "target_url": result.get("target_url"),
            "result": result.get("result")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/pocs/{poc_id}", summary="删除POC")
async def delete_poc(poc_id: int):
    """删除指定的POC"""
    success = poc_library_service.delete_poc(poc_id)
    if not success:
        raise HTTPException(status_code=404, detail="POC不存在或删除失败")
    return {"success": True, "message": "POC删除成功"}


@router.get("/pocs/statistics", summary="获取POC库统计信息")
async def get_statistics():
    """获取POC库统计信息"""
    try:
        stats = poc_library_service.get_statistics()
        return {"success": True, "statistics": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pocs/vuln-types", summary="获取所有漏洞类型")
async def get_vuln_types():
    """获取所有漏洞类型及其数量"""
    try:
        types = poc_library_service.get_all_vuln_types()
        return {"success": True, "vuln_types": types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pocs/{poc_id}/code", summary="获取POC文件内容")
async def get_poc_code(poc_id: int):
    """
    获取指定POC的文件内容

    - **poc_id**: POC记录ID

    返回POC脚本的源代码内容，用于查看或下载
    """
    try:
        # 获取POC记录
        poc_record = poc_library_service.get_poc_by_id(poc_id)
        if not poc_record:
            raise HTTPException(status_code=404, detail="POC不存在")

        # 检查文件路径
        poc_file_path = poc_record.get('poc_file_path')
        if not poc_file_path:
            raise HTTPException(status_code=404, detail="POC文件路径不存在")

        # 转换为Path对象并检查文件是否存在
        file_path = Path(poc_file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"POC文件不存在: {poc_file_path}")

        # 读取文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
        except UnicodeDecodeError:
            # 如果UTF-8解码失败，尝试使用其他编码
            with open(file_path, 'r', encoding='gbk') as f:
                code = f.read()

        return {"success": True, "code": code}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取POC文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"读取POC文件失败: {str(e)}")

