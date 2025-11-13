"""
配置文件
"""
import os
from typing import Optional


class Settings:
    """应用配置"""

    # API配置
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000

    # 大模型配置 - 支持OpenAI API兼容接口
    LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY", "sk-ziniryxiofvzpizndecqalcftmcpccrropnimazjzrzvglgr")
    LLM_API_BASE: str = os.getenv("LLM_API_BASE", "https://api.siliconflow.cn/v1")

    # POC生成模型（GLM-4.6）
    LLM_MODEL_GENERATE: str = os.getenv("LLM_MODEL_GENERATE", "zai-org/GLM-4.6")

    # 代码评审模型（DeepSeek-R1）
    LLM_MODEL_EVALUATE: str = os.getenv("LLM_MODEL_EVALUATE", "deepseek-ai/DeepSeek-R1")

    # 通用配置
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = None  # 不限制生成长度

    # 安全警告
    SECURITY_WARNING: str = """
    ⚠️  警告：本工具仅用于授权的安全测试和研究目的
    - 仅在获得明确授权的系统上使用
    - 未经授权的测试可能违反法律
    - 使用者需对其行为负责
    """


settings = Settings()