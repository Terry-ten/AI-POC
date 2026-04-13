"""
全局配置文件
"""


class Settings:
    """应用配置"""

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000

    SECURITY_WARNING: str = """
    ⚠️  警告：本工具仅用于授权的安全测试和研究目的
    - 仅在获得明确授权的系统上使用
    - 未经授权的测试可能违反法律
    - 使用者需对其行为负责
    """


settings = Settings()
