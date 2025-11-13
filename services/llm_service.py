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
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

        # 模型配置
        self.model_generate = settings.LLM_MODEL_GENERATE  # 生成模型
        self.model_evaluate = settings.LLM_MODEL_EVALUATE  # 评审模型

        # 初始化 AsyncOpenAI 客户端（兼容硅基流动API）
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base
        )

    async def generate_initial_poc(
        self, vulnerability_info: str, target_info: Optional[str] = None
    ) -> Dict[str, Optional[str]]:
        """
        第一步：使用 GLM-4.6 生成初始POC代码

        Args:
            vulnerability_info: 漏洞信息（描述、数据包、CVE等）
            target_info: 目标系统信息（可选）

        Returns:
            包含poc_code、explanation等的字典
        """
        try:
            # 构建prompt
            prompt = self._build_prompt(vulnerability_info, target_info)

            # 调用 GLM-4.6 API
            response = await self._call_llm_api(prompt, model=self.model_generate)

            return {
                "vulnerability_type": response.get("vulnerability_type"),
                "original_vulnerability_info": response.get("original_vulnerability_info"),
                "poc_code": response.get("poc_code"),
                "explanation": response.get("explanation"),
            }

        except Exception as e:
            raise Exception(f"生成初始POC代码失败: {str(e)}")

    async def evaluate_poc_code(self, prompt_content: str) -> str:
        """
        第二步：使用 DeepSeek-R1 评审POC代码

        Args:
            prompt_content: 包含漏洞信息、代码、逻辑介绍的完整prompt

        Returns:
            评审意见字符串
        """
        try:
            evaluation_prompt = f"""你是一个资深的网络安全专家和代码审查员。请仔细审查以下POC验证代码。

{prompt_content}

请从以下几个方面进行评审：

1. **代码合理性**：代码逻辑是否合理，是否符合该漏洞类型的验证方式
2. **有效性**：代码能否有效地验证漏洞是否存在
3. **完备性**：是否包含了必要的异常处理、参数验证、返回值检查
4. **安全性**：是否包含破坏性操作或过于激进的测试方法
5. **代码质量**：代码规范、注释清晰度、可读性

请提供具体的修改建议，包括：
- 需要修改的代码部分
- 修改的原因
- 建议的改进方案

请以结构化的方式返回评审意见。"""

            # 调用 DeepSeek-R1 API
            response = await self._call_llm_api_raw(evaluation_prompt, model=self.model_evaluate)

            return response

        except Exception as e:
            raise Exception(f"评审POC代码失败: {str(e)}")

    async def regenerate_poc_code(self, evaluate_content: str) -> Dict[str, Optional[str]]:
        """
        第三步：使用 GLM-4.6 根据评审意见重新生成POC代码

        Args:
            evaluate_content: 包含原始prompt和评审意见的完整内容

        Returns:
            包含最终poc_code、explanation等的字典
        """
        try:
            regenerate_prompt = f"""{evaluate_content}

请根据以上漏洞信息、初始代码和评审意见，重新生成一个改进后的POC验证代码。

要求：
1. 充分考虑评审意见中提出的问题
2. 保持原有的验证逻辑，但改进代码质量
3. 确保代码符合之前定义的 scan(url) 函数格式
4. 返回格式仍然是JSON

请以JSON格式返回，包含以下字段：
{{
  "vulnerability_type": "漏洞类型",
  "original_vulnerability_info": "原始漏洞信息",
  "poc_code": "改进后的完整scan函数代码",
  "explanation": "改进说明和使用方法"
}}
"""

            # 调用 GLM-4.6 API
            response = await self._call_llm_api(regenerate_prompt, model=self.model_generate)

            return {
                "vulnerability_type": response.get("vulnerability_type"),
                "original_vulnerability_info": response.get("original_vulnerability_info"),
                "poc_code": response.get("poc_code"),
                "explanation": response.get("explanation"),
            }

        except Exception as e:
            raise Exception(f"重新生成POC代码失败: {str(e)}")

    def _build_prompt(self, vulnerability_info: str, target_info: Optional[str]) -> str:
        """构建发送给大模型的提示词"""
        target_section = (
            f"\n目标系统信息：{target_info}\n" if target_info else ""
        )

        prompt = f"""你是一个Web安全研究专家，专注于Web应用程序漏洞分析和漏洞验证脚本编写。

⚠️ 重要提示：生成的代码仅用于授权的安全测试和研究目的，不得包含攻击性行为。

## 漏洞信息：
{vulnerability_info}
{target_section}

## 任务要求：

请根据以上漏洞描述和数据包信息，生成一个用于验证该漏洞是否存在的Python脚本。

### 严格的代码格式要求：

1. **函数签名** (必须严格遵守)：
   - 函数名必须为：`scan`
   - 接受一个参数：`url` (字符串类型，格式为标准URL：http(s)://x.x.x.x:port/)
   - 该URL已经被系统标准化处理，可以直接使用

2. **函数返回值** (必须严格遵守)：
   - 返回一个字典，包含以下字段：
     * `vulnerable`：布尔值，True表示存在漏洞，False表示不存在
     * `reason`：字符串，说明判断依据(例如："检测到SQL错误回显"、"成功执行XSS脚本"、"响应中包含敏感文件内容"等)
     * `details`：字符串，可选，提供更详细的检测过程和结果

   示例返回值：
   ```python
   return {{
       "vulnerable": True,
       "reason": "检测到SQL错误回显：'You have an error in your SQL syntax'",
       "details": "在username参数中注入单引号后，响应返回了MySQL错误信息"
   }}
   ```

3. **验证逻辑要求**：
   - 使用Python + requests库
   - 必须包含漏洞验证逻辑（不能只发送请求，要判断响应）
   - 使用安全的、无害的Payload进行验证（例如：时间盲注用sleep(1)而不是sleep(100)）
   - **不得包含任何破坏性操作**：不能删除数据、上传真实木马、执行危险命令等
   - 包含适当的异常处理，确保函数在任何情况下都能正常返回结果
   - 由于各url存在个性化差异，可以考虑可以设置多种不同的验证方法

4. **代码质量**：
   - 添加清晰的注释，说明每一步的目的
   - 使用合理的超时设置（建议5-10秒）
   - 处理各种异常情况（网络错误、超时、无效响应等）

5. **函数逻辑介绍**：
   - 在代码开头用文档字符串（docstring）说明该函数的验证逻辑
   - 说明使用的验证方法和判断依据

### 代码示例框架：

```python
import requests
import re
from urllib.parse import urljoin

def scan(url):
    \"\"\"
    漏洞验证函数

    漏洞类型：[这里填写漏洞类型]
    验证逻辑：[这里说明验证的具体方法和判断依据]

    参数：
        url: 目标URL（标准格式：http(s)://x.x.x.x:port/）

    返回：
        dict: {{"vulnerable": bool, "reason": str, "details": str}}
    \"\"\"
    try:
        # 在这里实现验证逻辑
        # ...

        return {{
            "vulnerable": True/False,
            "reason": "判断原因",
            "details": "详细说明"
        }}
    except Exception as e:
        return {{
            "vulnerable": False,
            "reason": f"扫描过程发生错误：{{str(e)}}",
            "details": ""
        }}
```

请以JSON格式返回，包含以下字段：
{{
  "vulnerability_type": "漏洞类型（如：SQL注入、XSS、文件上传等）",
  "original_vulnerability_info": "原始漏洞信息（直接复制用户提供的漏洞描述内容）",
  "poc_code": "完整的scan函数Python代码（必须包含函数定义和所有必要的import语句）",
  "explanation": "函数逻辑介绍：说明验证方法、使用的Payload、判断依据和注意事项"
}}
"""
        return prompt

    async def _call_llm_api(self, prompt: str, model: str = None) -> Dict[str, str]:
        """
        调用大模型API（使用OpenAI SDK）- 返回JSON格式

        支持OpenAI兼容的API接口（如硅基流动）
        """
        if model is None:
            model = self.model_generate

        try:
            logger.info("=" * 60)
            logger.info("开始调用大模型API")
            logger.info(f"API Base: {self.api_base}")
            logger.info(f"Model: {model}")
            logger.info(f"Temperature: {self.temperature}")
            logger.info(f"Max Tokens: {self.max_tokens}")
            logger.info(f"Prompt 长度: {len(prompt)} 字符")

            # 使用 OpenAI SDK 调用 API
            logger.info("正在发送请求到大模型...")

            # 构建API参数
            api_params = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的Web安全研究专家，精通Web应用程序漏洞分析和POC编写。请严格按照JSON格式返回结果，并确保在返回的JSON中包含用户提供的原始漏洞信息。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": self.temperature,
            }

            # 只在max_tokens不为None时添加该参数
            if self.max_tokens is not None:
                api_params["max_tokens"] = self.max_tokens

            response = await self.client.chat.completions.create(**api_params)

            logger.info("✅ 成功收到大模型响应")

            # 提取响应内容
            content = response.choices[0].message.content
            logger.info(f"响应内容长度: {len(content)} 字符")
            logger.debug(f"响应内容预览: {content[:200]}...")

            # 尝试解析JSON响应
            try:
                # 先尝试清理可能存在的markdown代码块标记
                cleaned_content = content.strip()
                if cleaned_content.startswith("```json"):
                    cleaned_content = cleaned_content[7:]
                if cleaned_content.startswith("```"):
                    cleaned_content = cleaned_content[3:]
                if cleaned_content.endswith("```"):
                    cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()

                parsed_content = json.loads(cleaned_content)

                # 清理poc_code字段中可能存在的markdown代码块标记
                if "poc_code" in parsed_content and parsed_content["poc_code"]:
                    poc_code = parsed_content["poc_code"].strip()
                    # 移除开头的代码块标记
                    if poc_code.startswith("```python"):
                        poc_code = poc_code[9:]
                    elif poc_code.startswith("```"):
                        poc_code = poc_code[3:]
                    # 移除结尾的代码块标记
                    if poc_code.endswith("```"):
                        poc_code = poc_code[:-3]
                    parsed_content["poc_code"] = poc_code.strip()

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

    async def _call_llm_api_raw(self, prompt: str, model: str = None) -> str:
        """
        调用大模型API（使用OpenAI SDK）- 返回原始文本

        用于评审等不需要JSON格式的场景
        """
        if model is None:
            model = self.model_evaluate

        try:
            logger.info("=" * 60)
            logger.info("开始调用大模型API（原始文本模式）")
            logger.info(f"API Base: {self.api_base}")
            logger.info(f"Model: {model}")
            logger.info(f"Temperature: {self.temperature}")
            logger.info(f"Max Tokens: {self.max_tokens}")

            # 使用 OpenAI SDK 调用 API
            logger.info("正在发送请求到大模型...")

            # 构建API参数
            api_params = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个资深的网络安全专家和代码审查员，请提供专业的代码评审意见。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": self.temperature,
            }

            # 只在max_tokens不为None时添加该参数
            if self.max_tokens is not None:
                api_params["max_tokens"] = self.max_tokens

            response = await self.client.chat.completions.create(**api_params)

            logger.info("✅ 成功收到大模型响应")

            # 提取响应内容
            content = response.choices[0].message.content
            logger.info(f"响应内容长度: {len(content)} 字符")
            logger.info("=" * 60)

            return content

        except Exception as e:
            # 提供更详细的错误信息
            error_type = type(e).__name__
            error_msg = str(e)

            logger.error("=" * 60)
            logger.error(f"❌ API调用失败")
            logger.error(f"异常类型: {error_type}")
            logger.error(f"错误详情: {error_msg}")

            logger.error("=" * 60)

            raise Exception(f"API调用异常: {error_type} - {error_msg}")


# 创建全局服务实例
llm_service = LLMService()