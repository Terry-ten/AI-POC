"""
大模型服务 - 负责与LLM API交互
"""
from openai import AsyncOpenAI
from typing import Optional, Dict
from config import settings
import json
import logging

# 配置日志
logger = logging.getLogger(__name__)


class LLMService:
    """大模型API调用服务"""

    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.api_base = settings.LLM_API_BASE
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

        # 初始化 AsyncOpenAI 客户端（兼容硅基流动API）
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base
        )

    async def generate_poc_code(
        self, vulnerability_info: str, target_info: Optional[str] = None
    ) -> Dict[str, Optional[str]]:
        """
        根据漏洞信息生成POC验证代码

        Args:
            vulnerability_info: 漏洞信息（描述、数据包、CVE等）
            target_info: 目标系统信息（可选）

        Returns:
            包含poc_code和explanation的字典
        """
        try:
            # 构建prompt
            prompt = self._build_prompt(vulnerability_info, target_info)

            # 调用LLM API
            response = await self._call_llm_api(prompt)

            return {
                "vulnerability_type": response.get("vulnerability_type"),
                "original_vulnerability_info": response.get("original_vulnerability_info"),
                "poc_code": response.get("poc_code"),
                "explanation": response.get("explanation"),
            }

        except Exception as e:
            raise Exception(f"生成POC代码失败: {str(e)}")

    def _build_prompt(self, vulnerability_info: str, target_info: Optional[str]) -> str:
        """构建发送给大模型的提示词"""
        target_section = (
            f"\n目标系统信息：{target_info}\n" if target_info else ""
        )

        prompt = f"""你是一个Web安全研究专家，专注于Web应用程序漏洞分析和POC编写。基于以下漏洞信息，生成对应的Web漏洞POC验证代码。

⚠️ 重要提示：生成的代码仅用于授权的安全测试和研究目的。

漏洞信息：
{vulnerability_info}
{target_section}
请根据以下要求生成POC验证代码：

1. **漏洞类型识别**：判断这是哪种Web漏洞（SQL注入、XSS、CSRF、文件上传、命令注入、SSRF、XXE、反序列化等）

2. **POC代码生成**：
   - 使用Python + requests库（优先）
   - 包含完整的HTTP请求（URL、Headers、Body）
   - 如果用户提供的是HTTP数据包，解析并转换为Python代码
   - 生成可以验证漏洞存在的测试代码（不是利用代码）
   - 使用安全的Payload进行验证（例如：使用sleep(3)而不是实际破坏性操作）

3. **代码结构**：
   - 清晰的注释说明每一步
   - 异常处理
   - 漏洞验证逻辑（判断漏洞是否存在）
   - 输出验证结果

4. **使用说明**：
   - 如何运行代码
   - 需要修改的参数（目标URL等）
   - 预期的验证结果
   - 注意事项和风险提示

请以JSON格式返回，包含以下字段：
{{
  "vulnerability_type": "漏洞类型（如：SQL注入、XSS等）",
  "original_vulnerability_info": "原始漏洞信息（直接复制用户提供的内容）",
  "poc_code": "完整的Python POC验证代码",
  "explanation": "详细的代码说明、使用方法和注意事项"
}}
"""
        return prompt

    async def _call_llm_api(self, prompt: str) -> Dict[str, str]:
        """
        调用大模型API（使用OpenAI SDK）

        支持OpenAI兼容的API接口（如硅基流动）
        """
        try:
            logger.info("=" * 60)
            logger.info("开始调用大模型API")
            logger.info(f"API Base: {self.api_base}")
            logger.info(f"Model: {self.model}")
            logger.info(f"Temperature: {self.temperature}")
            logger.info(f"Max Tokens: {self.max_tokens}")
            logger.info(f"Prompt 长度: {len(prompt)} 字符")

            # 使用 OpenAI SDK 调用 API
            logger.info("正在发送请求到大模型...")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[  # type: ignore
                    {
                        "role": "system",
                        "content": "你是一个专业的Web安全研究专家，精通Web应用程序漏洞分析和POC编写。请严格按照JSON格式返回结果，并确保在返回的JSON中包含用户提供的原始漏洞信息。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            logger.info("✅ 成功收到大模型响应")

            # 提取响应内容
            content = response.choices[0].message.content
            logger.info(f"响应内容长度: {len(content)} 字符")
            logger.debug(f"响应内容预览: {content[:200]}...")

            # 尝试解析JSON响应
            try:
                parsed_content = json.loads(content)
                logger.info("✅ JSON解析成功")
                logger.info("=" * 60)
                return parsed_content
            except json.JSONDecodeError as json_err:
                logger.warning(f"JSON解析失败: {str(json_err)}")
                logger.info("将整个响应作为 poc_code 返回")
                logger.info("=" * 60)
                # 如果不是JSON格式，将整个内容作为poc_code返回
                return {
                    "poc_code": content,
                    "explanation": "代码已生成，请仔细审查后使用。",
                }

        except Exception as e:
            # 提供更详细的错误信息
            error_type = type(e).__name__
            error_msg = str(e)

            logger.error("=" * 60)
            logger.error(f"❌ API调用失败")
            logger.error(f"异常类型: {error_type}")
            logger.error(f"错误详情: {error_msg}")

            # 如果是 OpenAI SDK 的异常，提供更多信息
            if hasattr(e, 'response'):
                logger.error(f"HTTP状态码: {getattr(e.response, 'status_code', 'N/A')}")
                logger.error(f"响应内容: {getattr(e.response, 'text', 'N/A')[:500]}")

            logger.error("=" * 60)

            raise Exception(f"API调用异常: {error_type} - {error_msg}")


# 创建全局服务实例
llm_service = LLMService()