"""
Vulnerability to POC Generator API
基于大模型的Web漏洞POC生成系统

⚠️  警告：本工具仅用于授权的安全测试和研究目的
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes import router
from config import settings
import uvicorn
import logging
import time
from pathlib import Path

# 创建FastAPI应用
app = FastAPI(
    title="Web Vulnerability to POC Generator",
    description="基于大模型API的Web漏洞信息到POC代码生成系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api_server.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有HTTP请求和响应"""
    start_time = time.time()

    logger.info(f"收到请求: {request.method} {request.url}")
    logger.info(f"客户端: {request.client.host if request.client else 'unknown'}")

    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"响应状态: {response.status_code} | 耗时: {process_time:.3f}秒")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"请求处理异常: {type(e).__name__} - {str(e)}")
        logger.error(f"耗时: {process_time:.3f}秒")
        raise

# 配置CORS - 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请设置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
app.include_router(router, prefix="/api", tags=["POC Generator"])

# 获取前端静态文件路径
frontend_dir = Path(__file__).parent / "frontend"

# 挂载静态文件（CSS, JS, 资源文件）
app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(frontend_dir / "js")), name="js")
app.mount("/assets", StaticFiles(directory=str(frontend_dir / "assets")), name="assets")


@app.get("/")
async def root():
    """根路径 - 返回前端HTML页面"""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    else:
        # 如果前端文件不存在，返回API信息
        return {
            "message": "Web Vulnerability to POC Generator API",
            "description": "根据Web漏洞信息生成POC验证代码",
            "warning": settings.SECURITY_WARNING,
            "docs": "/docs",
            "health": "/api/health",
        }


if __name__ == "__main__":
    import sys
    import io

    # 修复Windows控制台编码问题
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    print(settings.SECURITY_WARNING)
    print(f"\n🚀 启动服务器: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"🌐 前端页面: http://{settings.API_HOST}:{settings.API_PORT}/")
    print(f"📚 API文档: http://{settings.API_HOST}:{settings.API_PORT}/docs\n")

    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info",
    )
