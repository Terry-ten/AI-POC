"""
大模型服务 - 负责与LLM API交互
"""
from openai import AsyncOpenAI
from typing import Optional, Dict
from config import settings
from pathlib import Path
import json
import logging

# 配置日志
logger = logging.getLogger(__name__)


class LLMService:
    """大模型API调用服务"""

    def __init__(self):
        # 配置文件路径
        self.config_file = Path(__file__).parent.parent / "pocs" / "llm_config.json"

        # 从配置文件加载或使用默认配置
        saved_config = self._load_config_from_file()

        if saved_config:
            logger.info("✅ 从配置文件加载LLM配置")
            self.api_key = saved_config.get("api_key", settings.LLM_API_KEY)
            self.api_base = saved_config.get("api_base", settings.LLM_API_BASE)
            self.temperature = saved_config.get("temperature", settings.LLM_TEMPERATURE)
            self.max_tokens = saved_config.get("max_tokens", settings.LLM_MAX_TOKENS)
            self.model = saved_config.get("model", settings.LLM_MODEL_GENERATE)
        else:
            logger.info("使用默认配置初始化LLM服务")
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

    def _load_config_from_file(self) -> Optional[Dict]:
        """
        从文件加载配置

        Returns:
            配置字典，如果文件不存在返回None
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"已从文件加载LLM配置: {self.config_file}")
                    return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
        return None

    def _save_config_to_file(self):
        """
        保存配置到文件
        """
        try:
            # 确保目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            config = {
                "api_key": self.api_key,
                "model": self.model,
                "api_base": self.api_base,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 配置已保存到文件: {self.config_file}")
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")
            raise

    def update_config(self, api_key: str, model_id: str, base_url: str,
                     temperature: float = 0.7, max_tokens: Optional[int] = None):
        """
        动态更新LLM配置并持久化到文件

        Args:
            api_key: API密钥
            model_id: 模型ID
            base_url: API基础URL
            temperature: 温度参数
            max_tokens: 最大token数
        """
        logger.info("=" * 60)
        logger.info("更新LLM配置")
        logger.info(f"新模型: {model_id}")
        logger.info(f"新Base URL: {base_url}")
        logger.info(f"温度: {temperature}")

        # 更新配置
        self.api_key = api_key
        self.model = model_id
        self.api_base = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens

        # 保存配置到文件（持久化）
        self._save_config_to_file()

        # 重新初始化客户端
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base
        )

        logger.info("✅ LLM客户端已重新初始化并保存配置")
        logger.info("=" * 60)

    def get_current_config(self) -> Dict[str, str]:
        """
        获取当前LLM配置（隐藏敏感信息）

        Returns:
            当前配置字典
        """
        # 隐藏API密钥，只显示前后几位
        api_key_preview = "未设置"
        if self.api_key:
            if len(self.api_key) > 10:
                api_key_preview = f"{self.api_key[:7]}...{self.api_key[-4:]}"
            else:
                api_key_preview = f"{self.api_key[:3]}***"

        return {
            "model_id": self.model,
            "base_url": self.api_base,
            "temperature": str(self.temperature),
            "max_tokens": str(self.max_tokens) if self.max_tokens else "无限制",
            "api_key_preview": api_key_preview
        }

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

        # 使用字符串拼接而不是 f-string 或 format，避免花括号冲突
        prompt = """你是Web安全专家，专注漏洞验证脚本编写。
⚠️ 仅用于授权安全测试，不得包含攻击性行为。

🔴 **JSON格式要求（极其重要）**：
- 必须返回**严格符合JSON规范**的格式
- 字符串内的特殊字符**必须转义**：
  - 双引号 → \\"
  - 反斜杠 → \\\\
  - 换行符 → \\n
  - 制表符 → \\t
- ⚠️ **禁止在JSON字符串内包含真实的换行符、未转义的引号等**
- ⚠️ **不要使用markdown代码块包裹JSON**（直接返回JSON对象）

## 漏洞信息
""" + vulnerability_info + """
""" + target_section + """
## 任务
**判断能否用Python脚本自动化验证，然后返回相应内容：**
✅ **可自动化**：能使用Python库（requests、selenium、BeautifulSoup from bs4、fuzzing工具如自定义fuzzer函数或标准库用于多路径探测等）、调用外部工具（subprocess）、创建文件、自动化浏览器等方式完成整个验证过程。⚠️ 明确禁止安装额外库（如“不得使用pip install”），所有代码必须依赖标准或预装库。
❌ **不可自动化**：需要人工交互、识别复杂验证码、物理设备操作、人工审批流程
### A. 可自动化 - 返回POC代码
**函数要求：**
```python
def scan(url): # url已标准化为 http(s)://host/ 或 http(s)://host:port/
    return {
        "vulnerable": True/False,
        "reason": "判断依据（必须中文）",
        "details": "详细信息（必须中文）"
    }
```
**⚠️ 关键注意事项（规则总结）：**
1. **f-string花括号规则**（重要！）：
   - **变量占位符**：使用**单花括号** `f"{url}"`、`f"{variable}"`
   - **Python字典**：使用**单花括号** `data = {"key": "value"}`、`return {"vulnerable": True}`
   - **f-string内的字面量花括号**：才用**双花括号** `f"JSON: {{'key': '{value}'}}"` 输出 `JSON: {'key': 'xxx'}`
   - ⚠️ **禁止**：对所有花括号加倍，这会导致语法错误
   - 示例（正确 vs 错误）：
     - 正确：`payload = f"{{'id': '{user_id}'}}"` （输出字面花括号）
     - 错误：`payload = f"{{{{'id': '{user_id}'}}}}"` （多余转义导致语法错误）
     - 正确：`return {"key": f"{var}"}` （单花括号字典 + 单花括号变量）
     - 强调：在poc_code中确保代码无SyntaxError，通过"心理模拟"代码执行来验证语法。
2. **远程命令执行验证（极重要）**：
   - ❌ **错误**：发送payload后，在本地检查文件 `open('/tmp/test')`（检查的是本地文件！）
   - ✅ **正确方法（按优先级排序）**：
     - **HTTP回显**（最优先）：执行whoami/id/pwd等命令，检查响应中是否包含命令结果
     - **报错回显**：触发错误信息，检查响应中是否包含系统错误（如路径、版本号等）
     - **Web文件访问**：写入特征文件到Web目录（如test.txt），通过HTTP访问验证
   - ⚠️ **不可自动化**：需要外部HTTP服务器回连、DNS日志服务、反弹shell监听 → verifiable=false
3. **多路径探测**：文件上传/API接口等漏洞，需自动尝试多个路径（/、/upload、/upload.php、/api/upload等）。使用BeautifulSoup解析响应以提取潜在路径，或自定义fuzzer函数生成变异。
4. **URL编码原则（命令注入/SQL注入等）**：
   - ❌ **禁止**：使用 `urllib.parse.quote()` 对整个payload编码
   - ✅ **正确**：只手动编码URL层面字符（空格→%20，<→%3C，>→%3E），保持语法字符不变（单引号、双引号、括号等）
   - 示例：`system('touch /tmp/file')` → `system('touch%20/tmp/file')`（只编码空格，单引号和括号不编码）
5. **特殊字节处理（空字节漏洞如CVE-2013-4547）**：
   - ❌ **错误**：使用requests发送 `"/file%00.php"`（服务器收到字符串"%00"）
   - ✅ **正确**：使用socket发送bytes `b"/file\\x00.php"`（服务器收到真实空字节）
   ```python
   import socket
   # 构造包含空字节的路径
   exploit_path = b'/file.gif \\x00.php'
   # 构造原始HTTP请求并通过socket发送
   http_request = b'GET ' + exploit_path + b' HTTP/1.1\\r\\n' + ...
   sock.sendall(http_request)
   ```
6. **API参数完整性**：很多API缺少必需参数会返回400错误，需先测试正常参数再注入payload
7. **需要认证的漏洞**：如果漏洞需要登录，但文档只提供了Web UI登录入口（如访问/entrance页面）或用户名密码，**没有明确说明API登录接口的URL和请求参数格式**，则标记为 verifiable=false，不要猜测API接口路径和参数。对于边缘案例如"需要多步交互的漏洞"（e.g., 先登录再注入）：如果有明确API登录接口，则自动化（使用requests处理session）；否则标记不可自动化，并提供手动登录步骤模板。
8. **验证方法优先级**：
   - SQL注入：报错注入 > 布尔盲注 > 联合查询注入（⚠️ **禁止使用时间盲注**）
   - RCE：HTTP回显 > 报错回显 > Web文件访问（⚠️ **禁止使用时间盲注**）
   - ⚠️ **严格禁止时间盲注**：不允许使用sleep()、WAITFOR DELAY、benchmark()等任何基于延迟的验证方法
   - 如果漏洞只能通过时间盲注验证，则标记为 verifiable=false
   - 脚本能自动完成整个验证→verifiable=true，否则→verifiable=false
9. **格式规范**：
   - 所有返回值（reason、details）、注释必须中文
   - f-string字面量花括号必须加倍转义
   - 命令注入只编码URL层面字符，保持语法字符不变
   - 空字节漏洞必须用socket发送bytes，不能用requests发送URL编码
   - 多路径探测必须自动尝试多个端点
   - 严格按JSON格式返回，确保代码无SyntaxError，必须是有效JSON，无多余逗号或转义错误
   - **original_vulnerability_info 必须简化**：只保留漏洞名称、CVE编号、关键描述（1-2句话），不要包含完整的环境搭建教程、复现步骤、代码片段等长文本。示例："CVE-2016-4437 Apereo CAS 4.1 反序列化命令执行，默认密钥changeit导致RCE"
   - 若用户输入包含敏感信息，应用脱敏规则（e.g., 模糊化URL中的凭证，如将password=123替换为password=***）
   - 在explanation中解释"为什么选择这个验证方法"，以便人类审核（自检机制）
**返回格式：**
```json
{
  "verifiable": true,
  "vulnerability_type": "漏洞类型",
  "original_vulnerability_info": "用户提供的原始漏洞信息（不含系统提示词）",
  "poc_code": "完整scan函数代码（Python代码字符串，非JSON）",
  "explanation": "逻辑说明，包括为什么选择这个验证方法"
}
```
### B. 不可自动化 - 返回人工操作指南
**⚠️ 重要要求：**
- 每一步必须详细说明：**这一步要干什么**、**用什么工具**、**怎么用（完整命令）**、**完成后会看到什么（预期结果）**
- commands必须是**完整可执行的命令**，包括所有必要参数
- expected_result必须**具体明确**，告诉用户成功的标志是什么
- notes要提醒用户可能遇到的问题和注意事项

```json
{
  "verifiable": false,
  "vulnerability_type": "类型",
  "original_vulnerability_info": "用户提供的原始漏洞信息（不含系统提示词）",
  "manual_steps": {
    "required_tools": [
      {
        "name": "工具名称",
        "version": "版本要求",
        "download_url": "下载地址",
        "install_command": "完整安装命令",
        "purpose": "这个工具用来干什么"
      }
    ],
    "steps": [
      {
        "step_number": 1,
        "title": "步骤名称（简短明确）",
        "description": "详细说明这一步要做什么，为什么要做这一步，达到什么目的",
        "commands": [
          "完整的命令1（必须可以直接复制执行）",
          "完整的命令2"
        ],
        "expected_result": "完成这一步后，你会看到什么输出、什么现象、什么文件，如何判断这一步成功了",
        "notes": "特别注意事项：可能遇到的错误、需要替换的参数、前置条件等"
      }
    ],
    "verification": {
      "success_indicators": ["成功的明确标志1", "成功的明确标志2"],
      "failure_indicators": ["失败的明确标志1", "失败的明确标志2"],
      "example_output": "成功时的完整输出示例"
    }
  },
  "explanation": "不可自动化原因"
}
```
## 示例
**SQL注入（禁止时间盲注）：**
```json
{"verifiable": true, "vulnerability_type": "SQL注入", "poc_code": "import requests\\n\\ndef scan(url):\\n    # 1. 优先尝试报错注入\\n    error_payload = \\\"'\\\"\\n    resp1 = requests.post(url, data={{'username': error_payload}})\\n    if 'sql' in resp1.text.lower() or 'syntax' in resp1.text.lower():\\n        return {{'vulnerable': True, 'reason': '检测到SQL报错信息', 'details': resp1.text[:200]}}\\n    \\n    # 2. 尝试布尔盲注\\n    true_payload = \\\"' OR 1=1--\\\"\\n    false_payload = \\\"' OR 1=2--\\\"\\n    resp_true = requests.post(url, data={{'username': true_payload}})\\n    resp_false = requests.post(url, data={{'username': false_payload}})\\n    if len(resp_true.text) != len(resp_false.text):\\n        return {{'vulnerable': True, 'reason': '检测到布尔盲注', 'details': '真假条件响应长度不同'}}\\n    \\n    # 3. 尝试联合查询注入\\n    union_payload = \\\"' UNION SELECT NULL,NULL--\\\"\\n    resp_union = requests.post(url, data={{'username': union_payload}})\\n    if resp_union.status_code == 200 and len(resp_union.text) > len(resp1.text):\\n        return {{'vulnerable': True, 'reason': '检测到联合查询注入', 'details': '联合查询返回额外数据'}}\\n    \\n    return {{'vulnerable': False, 'reason': '未检测到SQL注入', 'details': ''}}", "explanation": "SQL注入使用报错注入、布尔盲注、联合查询注入，严格禁止时间盲注"}
```
**RCE（禁止时间盲注）：**
```json
{"verifiable": true, "vulnerability_type": "远程命令执行", "poc_code": "import requests\\n\\ndef scan(url):\\n    # 1. 优先尝试命令回显\\n    payloads = [\\n        {'cmd': 'whoami', 'indicators': ['root', 'www-data', 'apache', 'nginx', 'administrator']},\\n        {'cmd': 'id', 'indicators': ['uid=', 'gid=']},\\n        {'cmd': 'pwd', 'indicators': ['/var/www', '/home', '/usr', 'C:']},\\n    ]\\n    for p in payloads:\\n        resp = requests.get(url, params={'cmd': p['cmd']}, timeout=5)\\n        for indicator in p['indicators']:\\n            if indicator in resp.text.lower():\\n                return {'vulnerable': True, 'reason': f'检测到{p[\\\"cmd\\\"]}命令回显', 'details': resp.text[:200]}\\n    \\n    # 2. 尝试报错回显\\n    error_payload = 'cat /etc/nonexistent12345'\\n    resp = requests.get(url, params={'cmd': error_payload})\\n    if 'no such file' in resp.text.lower() or '不存在' in resp.text:\\n        return {'vulnerable': True, 'reason': '检测到命令执行报错回显', 'details': resp.text[:200]}\\n    \\n    # 3. 尝试Web文件写入（如果有写权限）\\n    import random\\n    filename = f'test_{random.randint(1000,9999)}.txt'\\n    write_cmd = f'echo vulnerable > {filename}'\\n    requests.get(url, params={'cmd': write_cmd})\\n    check_resp = requests.get(f'{url}/{filename}')\\n    if 'vulnerable' in check_resp.text:\\n        return {'vulnerable': True, 'reason': 'Web文件写入验证成功', 'details': f'成功写入{filename}'}\\n    \\n    return {'vulnerable': False, 'reason': '未检测到RCE（已尝试回显、报错、文件写入）', 'details': ''}", "explanation": "RCE使用回显类方法（whoami/id/pwd）、报错回显、Web文件写入，严格禁止时间盲注"}
```
**XSS（跨站脚本，使用selenium自动化浏览器验证弹窗）：**
```json
{"verifiable": true, "vulnerability_type": "XSS", "poc_code": "from selenium import webdriver\\nfrom selenium.webdriver.common.by import By\\nfrom selenium.webdriver.chrome.options import Options\\n\\ndef scan(url):\\n    options = Options()\\n    options.headless = True\\n    driver = webdriver.Chrome(options=options)\\n    try:\\n        driver.get(url + '?param=<script>alert(\\'xss\\')</script>')\\n        alert = driver.switch_to.alert\\n        if alert.text == 'xss':\\n            alert.accept()\\n            return {'vulnerable': True, 'reason': '检测到XSS弹窗触发', 'details': 'alert(\\'xss\\')成功执行'}\\n    except:\\n        pass\\n    finally:\\n        driver.quit()\\n    return {'vulnerable': False, 'reason': '未检测到XSS', 'details': ''}", "explanation": "使用selenium自动化浏览器检查alert('xss')是否触发，避免实际攻击，只验证无害payload，选择此方法因为XSS需浏览器渲染"}
```
**文件上传：**
```json
{"verifiable": true, "vulnerability_type": "文件上传", "poc_code": "import requests\\n\\ndef scan(url):\\n    paths = ['/upload', '/api/upload', '/file/upload.php']\\n    for path in paths:\\n        full_url = url + path\\n        files = {'file': ('test.php', '<?php echo \"vulnerable\"; ?>')}\\n        resp = requests.post(full_url, files=files)\\n        if resp.status_code == 200:\\n            check_url = url + '/uploads/test.php'\\n            check_resp = requests.get(check_url)\\n            if 'vulnerable' in check_resp.text:\\n                return {'vulnerable': True, 'reason': '文件上传并执行成功', 'details': '检测到回显'}\\n    return {'vulnerable': False, 'reason': '未检测到文件上传漏洞', 'details': ''}", "explanation": "自动尝试多路径上传无害文件，检查是否可访问，选择此方法因为多路径探测覆盖常见端点"}
```
**SSRF（服务器端请求伪造）：**
```json
{"verifiable": true, "vulnerability_type": "SSRF", "poc_code": "import requests\\n\\ndef scan(url):\\n    # 尝试访问内部地址并检查回显\\n    payloads = [\\n        {'url': 'http://127.0.0.1', 'indicators': ['localhost', 'apache', 'nginx', 'iis']},\\n        {'url': 'http://localhost', 'indicators': ['localhost', 'apache', 'nginx', 'iis']},\\n        {'url': 'http://169.254.169.254/latest/meta-data/', 'indicators': ['ami-', 'instance-id']},\\n    ]\\n    for p in payloads:\\n        resp = requests.get(url + '?url=' + p['url'], timeout=10)\\n        for indicator in p['indicators']:\\n            if indicator in resp.text.lower():\\n                return {'vulnerable': True, 'reason': f'检测到SSRF访问内部资源', 'details': f'访问{p[\\\"url\\\"]}返回特征字符串'}\\n    return {'vulnerable': False, 'reason': '未检测到SSRF', 'details': ''}", "explanation": "发送内部URL payload，只检查回显特征，不使用时间延迟检测"}
```
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

            # ⚠️ DEBUG: 保存完整响应到临时文件（用于调试JSON解析失败）
            debug_file = Path(__file__).parent.parent / "pocs" / "metadata" / "last_llm_response.json"
            try:
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.debug(f"完整响应已保存到: {debug_file}")

                # 同时保存字节级调试信息
                debug_bytes_file = Path(__file__).parent.parent / "pocs" / "metadata" / "last_llm_response_bytes.txt"
                with open(debug_bytes_file, 'w', encoding='utf-8') as f:
                    f.write(f"内容长度: {len(content)} 字符\n")
                    f.write(f"字节长度: {len(content.encode('utf-8'))} 字节\n")
                    f.write(f"前100个字符:\n{content[:100]}\n\n")
                    f.write(f"后100个字符:\n{content[-100:]}\n\n")
                    # 检查是否有异常字符
                    f.write("字符统计:\n")
                    f.write(f"  换行符: {content.count(chr(10))}\n")
                    f.write(f"  回车符: {content.count(chr(13))}\n")
                    f.write(f"  双引号: {content.count(chr(34))}\n")
                    f.write(f"  反斜杠: {content.count(chr(92))}\n")
            except Exception as e:
                logger.warning(f"保存调试响应失败: {e}")

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
                logger.error("=" * 60)
                logger.error(f"❌ JSON解析失败: {str(json_err)}")
                logger.error(f"错误位置: 第{json_err.lineno}行，第{json_err.colno}列")
                logger.error(f"错误字符位置: {json_err.pos}")
                logger.error("⚠️ LLM返回了格式错误的JSON，可能原因：")
                logger.error("  1. JSON中包含未转义的特殊字符（换行、引号等）")
                logger.error("  2. API响应被截断")
                logger.error("  3. LLM生成了不符合JSON规范的内容")
                logger.error(f"完整响应已保存到: {debug_file}")
                logger.error("=" * 60)

                # ❌ 不要将整个响应作为 poc_code！
                # 抛出异常，让上层处理
                raise Exception(f"LLM返回了无效的JSON格式（{str(json_err)}），请检查 {debug_file} 排查问题")

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