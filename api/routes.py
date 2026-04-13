"""
API路由定义
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse, Response
from models.schemas import (
    VulnerabilityRequest, PocResponse, ScanRequest,
    LLMConfigRequest, LLMConfigResponse,
    OOBConfigRequest, OOBConfigResponse,
    AssetSourceConfigRequest, AssetSourceConfigResponse, AssetSourceImportRequest,
    NucleiScanRequest, NucleiScanResponse, NucleiStatusResponse, NucleiTaskCreateRequest,
    BatchTaskCreateRequest, BatchTaskActionResponse
)
from services.asset_source_service import asset_source_service
from services.llm_service import llm_service
from services.oob_service import oob_service
from services.poc_library_service import poc_library_service
from services.nuclei_service import nuclei_service
from services.batch_task_service import batch_task_service
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
    description="使用大模型生成POC代码（支持实时进度反馈）",
)
async def generate_poc(request: VulnerabilityRequest):
    """
    接收Web漏洞信息，生成POC代码（流式响应）

    流程：
    1. 使用大模型生成POC，保存到 POC库

    - **vulnerability_info**: 漏洞信息，可以是描述、CVE编号、HTTP数据包等
    """

    async def generate_stream():
        try:
            logger.info("="*80)
            logger.info("开始POC生成流程")
            logger.info("="*80)

            # 发送开始消息
            yield f"data: {json.dumps({'type': 'status', 'step': 0, 'message': '开始生成流程...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            # 获取当前配置的模型名称
            current_model = llm_service.model

            # 使用大模型生成POC
            yield f"data: {json.dumps({'type': 'status', 'step': 1, 'message': f'正在使用 {current_model} 生成POC代码...', 'status': 'active'}, ensure_ascii=False)}\n\n"
            logger.info(f"使用 {current_model} 生成POC...")

            initial_prompt = llm_service._build_prompt(request.vulnerability_info, request.target_info)
            result = await llm_service.generate_initial_poc(
                vulnerability_info=request.vulnerability_info,
                target_info=request.target_info,
            )
            review_enabled = bool(request.enable_second_review)
            review_applied = False
            review_error = None
            review_model = llm_service.review_model if review_enabled else None

            if review_enabled:
                try:
                    yield f"data: {json.dumps({'type': 'status', 'step': 1, 'message': '初稿生成完成', 'status': 'completed'}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'status', 'step': 2, 'message': f'正在使用 {llm_service.review_model} 进行二次审核...', 'status': 'active'}, ensure_ascii=False)}\n\n"
                    result = await llm_service.review_generated_poc(
                        vulnerability_info=request.vulnerability_info,
                        target_info=request.target_info,
                        initial_prompt=initial_prompt,
                        initial_result=result,
                    )
                    review_applied = True
                    yield f"data: {json.dumps({'type': 'status', 'step': 2, 'message': '二次审核完成，已应用改进结果', 'status': 'completed'}, ensure_ascii=False)}\n\n"
                except Exception as review_exc:
                    review_error = str(review_exc)
                    logger.warning(f"⚠ 二次审核失败，保留初稿：{review_error}")
                    yield f"data: {json.dumps({'type': 'status', 'step': 2, 'message': f'二次审核失败，已保留初稿：{review_error}', 'status': 'completed'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'status', 'step': 2, 'message': '未启用二次审核，已跳过', 'status': 'completed'}, ensure_ascii=False)}\n\n"

            verifiable = result.get("verifiable", True)
            dependency_check = None
            if verifiable and result.get("poc_code"):
                dependency_check = poc_library_service.check_poc_dependencies(result.get("poc_code"))

            # 保存到POC库
            try:
                poc_id = poc_library_service.save_poc(
                    vuln_type=result.get("vulnerability_type") or "unknown",
                    vuln_name=result.get("vulnerability_name"),
                    vuln_info=request.vulnerability_info,  # 原封不动使用用户输入的描述
                    poc_code=result.get("poc_code"),
                    explanation=result.get("explanation") or "",
                    poc_type="python" if verifiable else "manual",
                    tags=["auto-generated", "llm"],
                    metadata={"target_info": request.target_info},
                    verifiable=verifiable,
                    manual_steps=result.get("manual_steps"),
                    execution_mode=result.get("execution_mode"),
                    verification_method=result.get("verification_method"),
                    input_schema=result.get("input_schema"),
                )
                logger.info(f"✅ {'可验证POC' if verifiable else '��工操作指南'}已保存到库，ID: {poc_id}")
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
                vulnerability_name=result.get("vulnerability_name"),
                vulnerability_type=result.get("vulnerability_type"),
                original_vulnerability_info=result.get("original_vulnerability_info"),
                poc_code=result.get("poc_code"),
                explanation=result.get("explanation"),
                verifiable=result.get("verifiable", True),
                execution_mode=result.get("execution_mode") or ("url_only" if result.get("verifiable", True) else "manual_guide"),
                verification_method=result.get("verification_method") or ("direct" if result.get("verifiable", True) else "manual"),
                input_schema=result.get("input_schema"),
                manual_steps=result.get("manual_steps"),
                review_enabled=review_enabled,
                review_applied=review_applied,
                review_model=review_model,
                review_error=review_error,
                dependency_check=dependency_check,
                error=None,
                warning=settings.SECURITY_WARNING,
            )
            yield f"data: {json.dumps({'type': 'result', 'data': poc_response.model_dump()}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"❌ POC生成流程失败：{str(e)}")
            error_result = PocResponse(
                success=False,
                vulnerability_name=None,
                vulnerability_type=None,
                original_vulnerability_info=request.vulnerability_info,
                poc_code=None,
                explanation=None,
                execution_mode=None,
                verification_method=None,
                input_schema=None,
                review_enabled=request.enable_second_review,
                review_applied=False,
                review_model=llm_service.review_model if request.enable_second_review else None,
                review_error=None,
                dependency_check=None,
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
        result = poc_library_service.execute_poc(
            poc_id,
            request.target_url,
            runtime_params=request.runtime_params,
        )

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "执行失败"),
                "result": result.get("result"),
                "classification": result.get("classification"),
            }

        return {
            "success": True,
            "poc_id": poc_id,
            "target_url": result.get("target_url"),
            "result": result.get("result"),
            "classification": result.get("classification"),
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


@router.get("/pocs/{poc_id}/code", summary="获取POC文件内容")
async def get_poc_code(poc_id: int):
    """
    获取指定POC的文件��容

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


@router.post("/batch-tasks", summary="创建批量检测任务", response_model=BatchTaskActionResponse)
async def create_batch_task(request: BatchTaskCreateRequest):
    """创建批量检测任务并启动后台执行"""
    try:
        task = batch_task_service.create_task(
            target_urls=request.target_urls,
            poc_ids=request.poc_ids,
            concurrency=request.concurrency,
        )
        return BatchTaskActionResponse(
            success=True,
            message="批量任务已创建并开始执行",
            task=task,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建批量任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch-tasks", summary="获取批量任务列表")
async def list_batch_tasks(
    limit: int = 20,
    offset: int = 0,
    status: str = None,
    result_filter: str = None,
    keyword: str = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    """获取批量任务列表"""
    try:
        result = batch_task_service.list_tasks(
            limit=limit,
            offset=offset,
            status=status,
            result_filter=result_filter,
            keyword=keyword,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"获取批量任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch-tasks/{task_id}", summary="获取批量任务详情")
async def get_batch_task(task_id: int):
    """获取批量任务详情"""
    task = batch_task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="批量任务不存在")
    return {"success": True, "task": task}


@router.get("/batch-tasks/{task_id}/export", summary="导出批量任务报告")
async def export_batch_task_report(task_id: int, format: str = "html"):
    """导出批量任务报告，支持 html/json/txt。"""
    task = batch_task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="批量任务不存在")

    try:
        filename, content_type, content = batch_task_service.export_task_report(task_id, format)
        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"导出批量任务报告失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch-tasks/{task_id}/items", summary="获取批量任务子任务列表")
async def get_batch_task_items(
    task_id: int,
    status: str = None,
    keyword: str = None,
    limit: int = 200,
    offset: int = 0,
):
    """获取批量任务子任务列表"""
    task = batch_task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="批量任务不存在")

    try:
        result = batch_task_service.get_task_items(
            task_id=task_id,
            status=status,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"获取批量任务子任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch-tasks/{task_id}/items/{item_id}/detail", summary="获取批量任务子任务详情")
async def get_batch_task_item_detail(task_id: int, item_id: int):
    """获取单个批量子任务的详细结果"""
    task = batch_task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="批量任务不存在")

    try:
        item = batch_task_service.get_task_item_detail(task_id=task_id, item_id=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="该子任务没有可用详情")
        return {"success": True, "item": item}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取批量任务子任务详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-tasks/{task_id}/cancel", summary="取消批量任务", response_model=BatchTaskActionResponse)
async def cancel_batch_task(task_id: int):
    """取消批量任务"""
    success = batch_task_service.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="批量任务不存在")

    return BatchTaskActionResponse(
        success=True,
        message="批量任务已取消",
        task=batch_task_service.get_task(task_id),
    )



# ==================== LLM配置管理API ====================

@router.post("/config/llm", summary="更新LLM配置", response_model=LLMConfigResponse)
async def update_llm_config(config: LLMConfigRequest):
    """
    更新大模型API配置

    - **api_key**: API密钥
    - **model_id**: 模型ID（如: gpt-4, claude-3-sonnet）
    - **base_url**: API基础URL
    - **temperature**: 温度参数（可选）
    - **max_tokens**: 最大token数（可选）
    """
    try:
        logger.info("收到LLM配置更新请求")
        logger.info(f"模型ID: {config.model_id}")
        logger.info(f"Base URL: {config.base_url}")

        # 更新LLM服务配置
        llm_service.update_config(
            api_key=config.api_key,
            model_id=config.model_id,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )

        # 获取当前配置（隐藏敏感信息）
        current_config = llm_service.get_current_config()

        logger.info("✅ LLM配置更新成功")

        return LLMConfigResponse(
            success=True,
            message="LLM配置已更新并立即生效，配置已永久保存",
            current_config=current_config
        )

    except Exception as e:
        logger.error(f"更新LLM配置失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"更新LLM配置失败: {str(e)}"
        )


@router.get("/config/llm", summary="获取当前LLM配置")
async def get_llm_config():
    """
    获取当前大模型API配置（隐藏敏感信息）

    返回当前使用的模型ID、Base URL等配置信息
    """
    try:
        current_config = llm_service.get_current_config()

        return {
            "success": True,
            "config": current_config
        }
    except Exception as e:
        logger.error(f"获取LLM配置失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取LLM配置失败: {str(e)}"
        )


@router.post("/config/review-llm", summary="更新二次审核LLM配置", response_model=LLMConfigResponse)
async def update_review_llm_config(config: LLMConfigRequest):
    """更新二次审核大模型配置"""
    try:
        llm_service.update_review_config(
            api_key=config.api_key,
            model_id=config.model_id,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )

        return LLMConfigResponse(
            success=True,
            message="二次审核LLM配置已更新并立即生效，配置已永久保存",
            current_config=llm_service.get_current_review_config()
        )
    except Exception as e:
        logger.error(f"更新二次审核LLM配置失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"更新二次审核LLM配置失败: {str(e)}"
        )


@router.get("/config/review-llm", summary="获取当前二次审核LLM配置")
async def get_review_llm_config():
    """获取当前二次审核大模型配置"""
    try:
        return {
            "success": True,
            "config": llm_service.get_current_review_config()
        }
    except Exception as e:
        logger.error(f"获取二次审核LLM配置失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取二次审核LLM配置失败: {str(e)}"
        )


@router.post("/config/oob", summary="更新OOB配置", response_model=OOBConfigResponse)
async def update_oob_config(config: OOBConfigRequest):
    """更新OOB外带验证配置"""
    try:
        oob_service.update_config(
            enabled=config.enabled,
            provider=config.provider,
            interactsh_server=config.interactsh_server,
            interactsh_token=config.interactsh_token,
            ceye_token=config.ceye_token,
            ceye_base_url=config.ceye_base_url,
            poll_interval=config.poll_interval or 1.0,
            max_polls=config.max_polls or 3,
        )
        return OOBConfigResponse(
            success=True,
            message="OOB配置已更新并立即生效，配置已永久保存",
            current_config=oob_service.get_current_config(),
        )
    except Exception as e:
        logger.error("更新OOB配置失败: %s", e)
        raise HTTPException(status_code=500, detail=f"更新OOB配置失败: {str(e)}")


@router.get("/config/oob", summary="获取当前OOB配置")
async def get_oob_config():
    """获取当前OOB配置（隐藏敏感信息）"""
    try:
        return {
            "success": True,
            "config": oob_service.get_current_config()
        }
    except Exception as e:
        logger.error("获取OOB配置失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取OOB配置失败: {str(e)}")


@router.post("/config/asset-sources", summary="更新空间测绘配置", response_model=AssetSourceConfigResponse)
async def update_asset_source_config(config: AssetSourceConfigRequest):
    """更新空间测绘平台配置"""
    try:
        asset_source_service.update_provider_config(
            provider=config.provider,
            email=config.email,
            token=config.token,
            base_url=config.base_url,
        )
        return AssetSourceConfigResponse(
            success=True,
            message="空间测绘配置已更新并立即生效，配置已永久保存",
            current_config=asset_source_service.get_current_config(),
        )
    except Exception as e:
        logger.error("更新空间测绘配置失败: %s", e)
        raise HTTPException(status_code=500, detail=f"更新空间测绘配置失败: {str(e)}")


@router.get("/config/asset-sources", summary="获取当前空间测绘配置")
async def get_asset_source_config():
    """获取当前空间测绘平台配置"""
    try:
        return {
            "success": True,
            "config": asset_source_service.get_current_config(),
        }
    except Exception as e:
        logger.error("获取空间测绘配置失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取空间测绘配置失败: {str(e)}")


@router.post("/asset-sources/import", summary="从空间测绘平台导入目标")
async def import_targets_from_asset_source(request: AssetSourceImportRequest):
    """从 FOFA / Hunter / Quake 导入目标 URL。"""
    try:
        result = asset_source_service.import_targets(
            provider=request.provider,
            query=request.query,
            pages=request.pages,
        )
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("导入空间测绘目标失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Nuclei 扫描 API ====================

@router.get("/nuclei/status", summary="检查 Nuclei 状态")
async def check_nuclei_status():
    """
    检查 Nuclei 是否可用

    返回 Nuclei 版本信息和可用模板数量
    """
    try:
        status_info = nuclei_service.check_nuclei_available()
        templates_count = nuclei_service.get_total_template_count()

        return {
            "available": status_info.get("available", False),
            "version": status_info.get("version"),
            "path": status_info.get("path"),
            "error": status_info.get("error"),
            "templates_count": templates_count
        }
    except Exception as e:
        logger.error(f"检查 Nuclei 状态失败: {str(e)}")
        return {
            "available": False,
            "error": str(e),
            "templates_count": 0
        }


@router.get("/nuclei/folders", summary="获取模板文件夹结构")
async def get_nuclei_folders():
    """
    获取模板文件夹结构

    返回文件夹列表，包含文件夹名称和模板数量
    """
    try:
        folders = nuclei_service.get_folder_structure()
        return {
            "success": True,
            "folders": folders
        }
    except Exception as e:
        logger.error(f"获取文件夹结构失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nuclei/templates", summary="分页获取模板列表")
async def get_nuclei_templates(
    folder: str = "",
    page: int = 1,
    page_size: int = 100,
    keyword: str = ""
):
    """
    分页获取指定文件夹的模板

    - **folder**: 文件夹路径（相对路径，空字符串表示根目录）
    - **page**: 页码，从1开始
    - **page_size**: 每页数量，默认100
    - **keyword**: 搜索关键词
    """
    try:
        templates, total = nuclei_service.get_templates_by_folder(
            folder=folder,
            page=page,
            page_size=page_size,
            keyword=keyword
        )
        return {
            "success": True,
            "templates": templates,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
        }
    except Exception as e:
        logger.error(f"获取 Nuclei 模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nuclei/template/content", summary="获取模板文件内容")
async def get_nuclei_template_content(path: str):
    """
    获取指定模板的 YAML 文件内容

    - **path**: 模板相对路径
    """
    content = nuclei_service.get_template_content(path)
    if content is None:
        raise HTTPException(status_code=404, detail=f"模板不存在: {path}")
    return {"success": True, "content": content}


@router.post("/nuclei/scan", summary="执行 Nuclei 扫描")
async def nuclei_scan(request: NucleiScanRequest):
    """
    使用 Nuclei 扫描目标 URL

    - **target_url**: 目标URL
    - **template_paths**: 要使用的模板路径列表（可选）
    - **folder**: 要扫描的文件夹（可选）
    - **timeout**: 扫描超时时间（秒）
    """
    try:
        logger.info(f"开始 Nuclei 扫描: {request.target_url}")

        if request.template_paths:
            result = nuclei_service.scan_multiple(
                target_url=request.target_url,
                template_paths=request.template_paths,
                timeout=request.timeout
            )
        elif request.folder is not None:
            result = nuclei_service.scan_folder(
                target_url=request.target_url,
                folder=request.folder,
                timeout=request.timeout
            )
        else:
            result = nuclei_service.scan_folder(
                target_url=request.target_url,
                folder="",
                timeout=request.timeout
            )

        return result

    except Exception as e:
        logger.error(f"Nuclei 扫描失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nuclei/tasks", summary="创建 Nuclei 扫描任务", response_model=BatchTaskActionResponse)
async def create_nuclei_task(request: NucleiTaskCreateRequest):
    """创建 Nuclei 任务化扫描，进入统一检测记录体系。"""
    try:
        template_paths = request.template_paths or []
        if request.folder is not None:
            templates, _ = nuclei_service.get_templates_by_folder(
                folder=request.folder,
                page=1,
                page_size=100000,
                keyword="",
            )
            template_paths = [item["relative_path"] for item in templates]

        task = batch_task_service.create_nuclei_task(
            target_urls=request.target_urls,
            template_paths=template_paths,
            concurrency=request.concurrency,
        )
        return BatchTaskActionResponse(
            success=True,
            message="Nuclei 扫描任务已创建并开始执行",
            task=task,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建 Nuclei 扫描任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nuclei/scan/stream", summary="流式执行 Nuclei 扫描")
async def nuclei_scan_stream(request: NucleiScanRequest):
    """
    流式执行 Nuclei 扫描，实时返回扫描进度和结果

    - **target_url**: 目标URL
    - **template_paths**: 要使用的模板路径列表（可选）
    - **folder**: 要扫描的文件夹（可选）
    - **timeout**: 扫描超时时间（秒）
    """

    async def generate_stream():
        try:
            async for event in nuclei_service.scan_stream_async(
                target_url=request.target_url,
                template_paths=request.template_paths,
                folder=request.folder,
                timeout=request.timeout
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Nuclei 流式扫描失败: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
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


@router.post("/nuclei/cache/clear", summary="清除模板缓存")
async def clear_nuclei_cache():
    """清除模板缓存，强制重新加载"""
    try:
        nuclei_service.clear_cache()
        return {"success": True, "message": "缓存已清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
