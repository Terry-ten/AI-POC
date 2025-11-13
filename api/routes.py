"""
API路由定义
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from models.schemas import VulnerabilityRequest, PocResponse, ScanRequest, ScanResponse
from services.llm_service import llm_service
from services.scanner_service import scanner_service
from services.poc_library_service import poc_library_service
from config import settings
import logging
import json
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/generate-poc",
    summary="生成并验证Web漏洞POC代码",
    description="三步流程：GLM-4.6生成初始POC → DeepSeek-R1评审 → GLM-4.6重新生成最终POC（支持实时进度反馈）",
)
async def generate_poc(request: VulnerabilityRequest):
    """
    接收Web漏洞信息，通过三步验证流程生成高质量POC代码（流式响应）

    流程：
    1. 使用 GLM-4.6 生成初始POC，保存到 testscan.py 和 prompt.txt
    2. 使用 DeepSeek-R1 评审代码，保存评审意见到 evaluate.txt
    3. 使用 GLM-4.6 根据评审重新生成，保存最终版本到 scan.py

    - **vulnerability_info**: 漏洞信息，可以是描述、CVE编号、HTTP数据包等
    - **target_info**: 目标系统信息（可选）
    """

    async def generate_stream():
        try:
            logger.info("="*80)
            logger.info("开始POC生成和验证流程")
            logger.info("="*80)

            # 发送开始消息
            yield f"data: {json.dumps({'type': 'status', 'step': 0, 'message': '开始生成流程...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            # ===== 第一步：使用 GLM-4.6 生成初始POC =====
            yield f"data: {json.dumps({'type': 'status', 'step': 1, 'message': '【第1步/3】正在使用 GLM-4.6 生成初始POC代码...'}, ensure_ascii=False)}\n\n"
            logger.info("【第1步/3】使用 GLM-4.6 生成初始POC...")

            initial_result = await llm_service.generate_initial_poc(
                vulnerability_info=request.vulnerability_info,
                target_info=request.target_info,
            )

            # 保存初始POC到 testscan.py 和 prompt.txt
            scanner_service.save_initial_poc(
                vulnerability_type=initial_result.get("vulnerability_type") or "未知类型",
                vulnerability_info=initial_result.get("original_vulnerability_info") or request.vulnerability_info,
                poc_code=initial_result.get("poc_code") or "",
                explanation=initial_result.get("explanation") or ""
            )
            logger.info("✅ 初始POC生成完成，已保存到 testscan.py 和 prompt.txt")
            yield f"data: {json.dumps({'type': 'status', 'step': 1, 'message': '✅ 第1步完成：初始POC已生成并保存'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            # ===== 第二步：使用 DeepSeek-R1 评审代码 =====
            yield f"data: {json.dumps({'type': 'status', 'step': 2, 'message': '【第2步/3】正在使用 DeepSeek-R1 评审代码质量...'}, ensure_ascii=False)}\n\n"
            logger.info("【第2步/3】使用 DeepSeek-R1 评审代码...")

            prompt_content = scanner_service.get_prompt_content()
            evaluation = await llm_service.evaluate_poc_code(prompt_content)

            # 保存评审意见到 evaluate.txt
            scanner_service.save_evaluation(evaluation)
            logger.info("✅ 代码评审完成，已保存到 evaluate.txt")
            yield f"data: {json.dumps({'type': 'status', 'step': 2, 'message': '✅ 第2步完成：代码评审已完成'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            # ===== 第三步：使用 GLM-4.6 根据评审重新生成 =====
            yield f"data: {json.dumps({'type': 'status', 'step': 3, 'message': '【第3步/3】正在使用 GLM-4.6 根据评审重新生成最终POC...'}, ensure_ascii=False)}\n\n"
            logger.info("【第3步/3】使用 GLM-4.6 根据评审重新生成POC...")

            evaluate_content = scanner_service.get_evaluate_content()
            final_result = await llm_service.regenerate_poc_code(evaluate_content)

            # 保存最终版本到 scan.py
            scanner_service.save_scan_function(
                vulnerability_type=final_result.get("vulnerability_type") or "未知类型",
                vulnerability_info=final_result.get("original_vulnerability_info") or request.vulnerability_info,
                poc_code=final_result.get("poc_code") or "",
                explanation=final_result.get("explanation") or ""
            )
            logger.info("✅ 最终POC生成完成，已保存到 scan.py")

            # 保存到POC库
            try:
                poc_id = poc_library_service.save_poc(
                    vuln_type=final_result.get("vulnerability_type") or "unknown",
                    vuln_info=final_result.get("original_vulnerability_info") or request.vulnerability_info,
                    poc_code=final_result.get("poc_code") or "",
                    explanation=final_result.get("explanation") or "",
                    poc_type="python",
                    tags=["auto-generated", "llm"],
                    metadata={"target_info": request.target_info}
                )
                logger.info(f"✅ POC已保存到库，ID: {poc_id}")
            except Exception as e:
                logger.warning(f"⚠ 保存到POC库失败：{str(e)}")

            yield f"data: {json.dumps({'type': 'status', 'step': 3, 'message': '✅ 第3步完成：最终POC已生成并保存到库'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            logger.info("="*80)
            logger.info("POC生成和验证流程完成")
            logger.info("="*80)

            # 发送最终结果
            result = PocResponse(
                success=True,
                vulnerability_type=final_result.get("vulnerability_type"),
                original_vulnerability_info=final_result.get("original_vulnerability_info"),
                poc_code=final_result.get("poc_code"),
                explanation=final_result.get("explanation"),
                error=None,
                warning=settings.SECURITY_WARNING,
            )
            yield f"data: {json.dumps({'type': 'result', 'data': result.model_dump()}, ensure_ascii=False)}\n\n"
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


@router.post(
    "/scan",
    response_model=ScanResponse,
    summary="执行漏洞扫描",
    description="使用已保存的 scan.py 脚本对目标URL进行漏洞验证",
)
async def scan_url(request: ScanRequest) -> ScanResponse:
    """
    执行漏洞扫描

    - **target_url**: 目标URL（将自动标准化为 http(s)://x.x.x.x:port/ 格式）

    注意：请先通过 /generate-poc 接口生成POC代码，系统会自动保存为 scan.py
    """
    try:
        # 执行扫描
        scan_result = scanner_service.execute_scan(
            target_url=request.target_url
        )

        if not scan_result.get("success"):
            return ScanResponse(
                success=False,
                target_url=request.target_url,
                vulnerable=False,
                reason="扫描执行失败",
                details=None,
                error=scan_result.get("error", "未知错误")
            )

        result_data = scan_result.get("result", {})
        return ScanResponse(
            success=True,
            target_url=scan_result.get("target_url"),
            vulnerable=result_data.get("vulnerable", False),
            reason=result_data.get("reason", "未提供判断原因"),
            details=result_data.get("details"),
            error=None
        )

    except Exception as e:
        return ScanResponse(
            success=False,
            target_url=request.target_url,
            vulnerable=False,
            reason="扫描执行异常",
            details=None,
            error=str(e)
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
    limit: int = 50,
    offset: int = 0
):
    """
    搜索POC库

    - **vuln_type**: 漏洞类型过滤（如: sqli, xss, rce）
    - **poc_type**: POC类型过滤（python/nuclei）
    - **keyword**: 关键词搜索
    - **limit**: 返回数量限制
    - **offset**: 偏移量
    """
    try:
        pocs = poc_library_service.search_pocs(
            vuln_type=vuln_type,
            poc_type=poc_type,
            keyword=keyword,
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

