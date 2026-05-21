"""
大模型服务 - 负责与LLM API交互
"""
from openai import AsyncOpenAI
from typing import Optional, Dict
from pathlib import Path
import json
import yaml
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 大模型默认配置
DEFAULT_LLM_CONFIG = {
    "api_key": None,
    "api_base": "https://api.siliconflow.cn/v1",
    "model": "Qwen/Qwen3-Coder-480B-A35B-Instruct",
    "temperature": 1,
    "max_tokens": None
}

LLM_REQUEST_TIMEOUT_SECONDS = 180


class LLMService:
    """大模型API调用服务"""

    def __init__(self):
        # 配置文件路径
        self.config_file = Path(__file__).parent.parent / "pocs" / "llm_config.json"
        self.review_config_file = Path(__file__).parent.parent / "pocs" / "review_llm_config.json"
        self.prompt_config_file = Path(__file__).parent.parent / "prompts" / "poc_generation.yaml"

        # 加载Prompt配置
        self.prompt_config = self._load_prompt_config()

        # 从配置文件加载或使用默认配置
        saved_config = self._load_config_from_file()

        if saved_config:
            logger.info("✅ 从配置文件加载LLM配置")
            self.api_key = saved_config.get("api_key", DEFAULT_LLM_CONFIG["api_key"])
            self.api_base = saved_config.get("api_base", DEFAULT_LLM_CONFIG["api_base"])
            self.temperature = saved_config.get("temperature", DEFAULT_LLM_CONFIG["temperature"])
            self.max_tokens = saved_config.get("max_tokens", DEFAULT_LLM_CONFIG["max_tokens"])
            self.model = saved_config.get("model", DEFAULT_LLM_CONFIG["model"])
        else:
            logger.info("使用默认配置初始化LLM服务")
            self.api_key = DEFAULT_LLM_CONFIG["api_key"]
            self.api_base = DEFAULT_LLM_CONFIG["api_base"]
            self.temperature = DEFAULT_LLM_CONFIG["temperature"]
            self.max_tokens = DEFAULT_LLM_CONFIG["max_tokens"]
            self.model = DEFAULT_LLM_CONFIG["model"]

        # 初始化 AsyncOpenAI 客户端（兼容硅基流动API）
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        )

        saved_review_config = self._load_json_config(self.review_config_file)
        self.review_api_key = None
        self.review_api_base = DEFAULT_LLM_CONFIG["api_base"]
        self.review_temperature = 0.3
        self.review_max_tokens = DEFAULT_LLM_CONFIG["max_tokens"]
        self.review_model = DEFAULT_LLM_CONFIG["model"]
        if saved_review_config:
            self.review_api_key = saved_review_config.get("api_key")
            self.review_api_base = saved_review_config.get("api_base", self.review_api_base)
            self.review_temperature = saved_review_config.get("temperature", self.review_temperature)
            self.review_max_tokens = saved_review_config.get("max_tokens", self.review_max_tokens)
            self.review_model = saved_review_config.get("model", self.review_model)

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

    def _load_json_config(self, config_file: Path) -> Optional[Dict]:
        try:
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败 {config_file}: {str(e)}")
        return None

    def _load_prompt_config(self) -> Dict:
        """
        从YAML文件加载Prompt配置

        Returns:
            Prompt配置字典
        """
        try:
            if self.prompt_config_file.exists():
                with open(self.prompt_config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    logger.info(f"已从文件加载Prompt配置: {self.prompt_config_file}")
                    return config
        except Exception as e:
            logger.error(f"加载Prompt配置文件失败: {str(e)}")
        # 返回空配置，将使用内置默认Prompt
        return {}

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

    def _save_review_config_to_file(self):
        try:
            self.review_config_file.parent.mkdir(parents=True, exist_ok=True)
            config = {
                "api_key": self.review_api_key,
                "model": self.review_model,
                "api_base": self.review_api_base,
                "temperature": self.review_temperature,
                "max_tokens": self.review_max_tokens,
            }
            with open(self.review_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存二次审核配置文件失败: {str(e)}")
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
            base_url=self.api_base,
            timeout=LLM_REQUEST_TIMEOUT_SECONDS,
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

    def update_review_config(self, api_key: str, model_id: str, base_url: str,
                            temperature: float = 0.3, max_tokens: Optional[int] = None):
        self.review_api_key = api_key
        self.review_model = model_id
        self.review_api_base = base_url
        self.review_temperature = temperature
        self.review_max_tokens = max_tokens
        self._save_review_config_to_file()

    def get_current_review_config(self) -> Dict[str, str]:
        api_key_preview = "未设置"
        if self.review_api_key:
            if len(self.review_api_key) > 10:
                api_key_preview = f"{self.review_api_key[:7]}...{self.review_api_key[-4:]}"
            else:
                api_key_preview = f"{self.review_api_key[:3]}***"

        return {
            "model_id": self.review_model,
            "base_url": self.review_api_base,
            "temperature": str(self.review_temperature),
            "max_tokens": str(self.review_max_tokens) if self.review_max_tokens else "无限制",
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
                "vulnerability_name": response.get("vulnerability_name"),
                "vulnerability_type": response.get("vulnerability_type"),
                "original_vulnerability_info": response.get("original_vulnerability_info"),
                "poc_code": response.get("poc_code"),
                "execution_mode": response.get("execution_mode"),
                "verification_method": response.get("verification_method"),
                "input_schema": response.get("input_schema"),
                "manual_steps": response.get("manual_steps"),
                "explanation": response.get("explanation"),
            }

        except Exception as e:
            # 直接向上抛出，避免重复包装错误信息
            raise Exception(f"生成POC代码失败: {str(e)}")

    async def review_generated_poc(
        self,
        vulnerability_info: str,
        target_info: Optional[str],
        initial_prompt: str,
        initial_result: Dict[str, Optional[str]],
    ) -> Dict[str, Optional[str]]:
        if not self.review_api_key or not self.review_model or not self.review_api_base:
            raise Exception("二次审核已开启，但未配置二次审核模型")

        prompt = self._build_review_prompt(
            vulnerability_info=vulnerability_info,
            target_info=target_info,
            initial_prompt=initial_prompt,
            initial_result=initial_result,
        )
        response = await self._call_llm_api_with_settings(
            prompt=prompt,
            api_key=self.review_api_key,
            base_url=self.review_api_base,
            model=self.review_model,
            temperature=self.review_temperature,
            max_tokens=self.review_max_tokens,
            debug_filename="last_llm_review_response.json",
        )
        return {
            "verifiable": response.get("verifiable", initial_result.get("verifiable", True)),
            "vulnerability_name": response.get("vulnerability_name"),
            "vulnerability_type": response.get("vulnerability_type"),
            "original_vulnerability_info": response.get("original_vulnerability_info"),
            "poc_code": response.get("poc_code"),
            "execution_mode": response.get("execution_mode"),
            "verification_method": response.get("verification_method"),
            "input_schema": response.get("input_schema"),
            "manual_steps": response.get("manual_steps"),
            "explanation": response.get("explanation"),
        }

    def _build_prompt(self, vulnerability_info: str, target_info: Optional[str]) -> str:
        """构建发送给大模型的提示词（从配置文件或使用默认模板）"""
        target_section = f"\n目标系统信息：{target_info}\n" if target_info else ""

        # 如果有配置文件中的模板，使用字符串替换（避免format的花括号问题）
        if self.prompt_config and 'user_prompt_template' in self.prompt_config:
            template = self.prompt_config['user_prompt_template']
            return template.replace('{vulnerability_info}', vulnerability_info).replace('{target_section}', target_section)

        # 否则使用内置默认模板（简化版）
        return f"""你是Web安全专家，专注漏洞验证脚本编写。
警告：仅用于授权安全测试，不得包含攻击性行为。

JSON格式要求：必须返回严格符合JSON规范的格式，字符串内的特殊字符必须转义。

## 漏洞信息
{vulnerability_info}
{target_section}
## 任务
判断能否用Python脚本自动化验证，返回JSON格式结果。

规则补充：
- 对 SSRF、XXE、无回显RCE 等无回显漏洞，优先考虑平台 OOB helper，而不是直接判 manual
- 平台 OOB helper 用法：
  1) client = get_oob_client() 或 create_oob_client()
  2) probe = client.build_probe(protocol="http" 或 "dns")
  3) 将 probe["url"] 注入漏洞触发点
  4) verify_result = client.verify(probe["flag"], protocol="http" 或 "dns")
- 如果使用 OOB：
  - execution_mode 必须为 "url_only"
  - verification_method 必须为 "oob"
  - get_oob_client()/create_oob_client() 失败时不要吞掉异常，应把真实异常写入 reason 或 details
- 如果漏洞可自动化验证，但需要用户提供运行时参数（如 Cookie、Token、自定义 Header、请求体片段）：
  - verifiable 仍应为 true
  - execution_mode 必须为 "url_with_params"
  - verification_method 通常应为 "direct"
  - 必须返回 input_schema，字段至少包含 name、label、type、required、description
  - type 仅使用 text/password/textarea/json/select/checkbox
  - poc_code 必须通过 runtime_params 或 get_runtime_param() 读取这些参数，禁止写死
- 仅当漏洞必须依赖外部监听器、反弹shell、用户自建回连设施，且平台 OOB helper 无法覆盖时，才返回 manual
- 常规 HTTP 请求优先使用平台 HTTP helper：
  - create_http_client()
  - get_http_client()
  - http_request()
- 需要原始 HTTP 报文、特殊字节或协议细节控制时，优先使用 send_raw_http()
- 禁止在新生成 POC 里无必要地散写大量 requests.get()/post()
- 任意文件读取/路径穿越类漏洞：优先同时覆盖 Linux（如 /etc/passwd）和 Windows（如 windows/win.ini）常见目标文件，避免验证条件过窄
- poc_code 必须是可直接写入 .py 文件的多行源码，禁止返回整段字面量 \\n 的单行代码

可自动化时返回：
{{"verifiable": true, "vulnerability_name": "漏洞名称", "vulnerability_type": "类型", "original_vulnerability_info": "简化的漏洞信息", "execution_mode": "url_only 或 url_with_params", "verification_method": "direct 或 oob", "input_schema": null 或 [{{"name": "cookie", "label": "登录Cookie", "type": "textarea", "required": true, "description": "请输入有效Cookie"}}], "poc_code": "完整scan函数代码", "explanation": "逻辑说明"}}

不可自动化时返回：
{{"verifiable": false, "vulnerability_name": "漏洞名称", "vulnerability_type": "类型", "original_vulnerability_info": "简化的漏洞信息", "execution_mode": "manual_guide", "verification_method": "manual", "input_schema": null, "manual_steps": {{"required_tools": [...], "steps": [...], "verification": {{...}}}}, "explanation": "不可自动化原因"}}

scan函数格式：
def scan(url):
    return {{"vulnerable": True/False, "reason": "判断依据", "details": "详细信息"}}
"""

    def _build_review_prompt(
        self,
        vulnerability_info: str,
        target_info: Optional[str],
        initial_prompt: str,
        initial_result: Dict[str, Optional[str]],
    ) -> str:
        target_section = f"\n目标系统信息：{target_info}\n" if target_info else ""
        result_json = json.dumps(initial_result, ensure_ascii=False, indent=2)
        return f"""你是Web漏洞POC审核专家。你会对初稿POC做二次审核，只关注是否有明显逻辑错误、验证条件过窄、平台helper使用错误、执行模式判断错误。
  
  要求：
  - 你必须返回严格JSON
  - 输出结构必须与初次生成完全一致
  - 如果初稿没有明显问题，也必须返回等价且可直接使用的最终版本
  - 如果要改进，直接输出改进后的最终版，不要输出diff
  - 审核遵循“最小必要修改”原则；除非明确发现逻辑错误，不要重写整个触发链
  - 优先保持当前系统约束：默认仍是单POC、url_only/direct/oob/manual_guide 三种模式
  - 如果初稿已经给出与具体组件/接口/参数位强相关的高置信触发点（如特定查询参数、特定接口路径、特定表单字段），优先保留这些触发点，不要泛化成更宽但更弱的通用方案
  - 不要把已存在的参数注入、路径注入、接口参数注入方案，随意改成仅依赖通用 Header 注入的方案；只有漏洞信息明确表明 Header 才是主要触发位时才允许这样修改
  - 如果初稿已经选择了明确的 OOB 协议或触发路径，不要无根据地扩展成多协议并行探测
  - 若使用 OOB helper，不要吞掉初始化异常，应把真实异常写入 reason 或 details
  - 若使用 OOB helper，不要在 client.verify() 外再额外手写长轮询或重复重试循环，平台 helper 已负责轮询
  - 审核目标是修正明显错误并保留已验证有效的思路，不要为了“更通用”而降低对当前场景的命中概率
  
  原始漏洞信息：
  {vulnerability_info}
{target_section}
第一次大模型生成结果：
{result_json}

返回格式：
可自动化时：
{{"verifiable": true, "vulnerability_name": "漏洞名称", "vulnerability_type": "类型", "original_vulnerability_info": "简化的漏洞信息", "execution_mode": "url_only 或 url_with_params", "verification_method": "direct 或 oob", "input_schema": null 或 [...], "poc_code": "完整scan函数代码", "explanation": "审核后的最终说明"}}

不可自动化时：
{{"verifiable": false, "vulnerability_name": "漏洞名称", "vulnerability_type": "类型", "original_vulnerability_info": "简化的漏洞信息", "execution_mode": "manual_guide", "verification_method": "manual", "input_schema": null, "manual_steps": {{"required_tools": [...], "steps": [...], "verification": {{...}}}}, "explanation": "审核后的最终说明"}}
"""

    def _parse_llm_json_response(self, content: str, debug_file: Path) -> Dict:
        """
        解析LLM返回的JSON响应，处理常见的格式问题

        Args:
            content: LLM返回的原始内容
            debug_file: 调试文件路径（用于错误提示）

        Returns:
            解析后的字典
        """
        # 1. 清理markdown代码块标记
        cleaned_content = content.strip()
        if cleaned_content.startswith("```json"):
            cleaned_content = cleaned_content[7:]
        if cleaned_content.startswith("```"):
            cleaned_content = cleaned_content[3:]
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-3]
        cleaned_content = cleaned_content.strip()

        # 2. 修复JSON字符串中未转义的控制字符
        # 这是LLM常见的问题：在字符串值中直接换行而不是使用\n
        def fix_control_chars_in_strings(json_str: str) -> str:
            """修复JSON字符串值中的未转义控制字符"""
            result = []
            in_string = False
            escape_next = False
            i = 0

            while i < len(json_str):
                char = json_str[i]

                if escape_next:
                    result.append(char)
                    escape_next = False
                elif char == '\\':
                    result.append(char)
                    escape_next = True
                elif char == '"':
                    result.append(char)
                    in_string = not in_string
                elif in_string and char in '\n\r\t':
                    # 在字符串内部的控制字符需要转义
                    if char == '\n':
                        result.append('\\n')
                    elif char == '\r':
                        result.append('\\r')
                    elif char == '\t':
                        result.append('\\t')
                else:
                    result.append(char)

                i += 1

            return ''.join(result)

        # 3. 尝试解析，如果失败则修复后重试
        try:
            parsed_content = json.loads(cleaned_content)
        except json.JSONDecodeError as first_err:
            # 尝试修复控制字符后重新解析
            try:
                fixed_content = fix_control_chars_in_strings(cleaned_content)
                parsed_content = json.loads(fixed_content)
                logger.info("⚠️ JSON包含未转义的控制字符，已自动修复")
            except json.JSONDecodeError as json_err:
                logger.error("=" * 60)
                logger.error(f"❌ JSON解析失败: {str(json_err)}")
                logger.error(f"错误位置: 第{json_err.lineno}行，第{json_err.colno}列")
                logger.error(f"完整响应已保存到: {debug_file}")
                logger.error("=" * 60)
                raise Exception(f"LLM返回了无效的JSON格式（{str(first_err)}），请检查 {debug_file}")

        # 4. 清理poc_code字段中可能存在的markdown代码块标记
        if "poc_code" in parsed_content and parsed_content["poc_code"]:
            poc_code = parsed_content["poc_code"].strip()
            if poc_code.startswith("```python"):
                poc_code = poc_code[9:]
            elif poc_code.startswith("```"):
                poc_code = poc_code[3:]
            if poc_code.endswith("```"):
                poc_code = poc_code[:-3]
            poc_code = self._normalize_poc_code_string(poc_code)
            parsed_content["poc_code"] = poc_code.strip()

        return parsed_content

    def _normalize_poc_code_string(self, poc_code: str) -> str:
        """
        处理模型把代码换行双重转义成字面量 \\n / \\t 的情况。

        仅在代码中不存在真实换行、但包含明显的字面量转义时做修复，
        避免误伤正常代码里的反斜杠。
        """
        if not poc_code:
            return poc_code

        has_real_newline = "\n" in poc_code
        has_literal_newline = "\\n" in poc_code or "\\r\\n" in poc_code
        has_literal_tab = "\\t" in poc_code

        if has_real_newline or not (has_literal_newline or has_literal_tab):
            return poc_code

        normalized = poc_code.replace("\\r\\n", "\n")
        normalized = normalized.replace("\\n", "\n")
        normalized = normalized.replace("\\t", "\t")
        return normalized

    async def _call_llm_api(self, prompt: str, model: str = None) -> Dict[str, str]:
        """
        调用大模型API（使用OpenAI SDK）- 返回JSON格式

        支持OpenAI兼容的API接口（如硅基流动）
        """
        return await self._call_llm_api_with_settings(
            prompt=prompt,
            api_key=self.api_key,
            base_url=self.api_base,
            model=model or self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            debug_filename="last_llm_response.json",
        )

    async def _call_llm_api_with_settings(
        self,
        prompt: str,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        debug_filename: str,
    ) -> Dict[str, str]:
        try:
            logger.info("=" * 60)
            logger.info("开始调用大模型API")
            logger.info(f"API Base: {base_url}")
            logger.info(f"Model: {model}")
            logger.info(f"Temperature: {temperature}")
            logger.info(f"Max Tokens: {max_tokens}")
            logger.info(f"Prompt 长度: {len(prompt)} 字符")

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=LLM_REQUEST_TIMEOUT_SECONDS,
            )
            api_params = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的Web安全研究专家，精通Web应用程序漏洞分析和POC编写。请严格按照JSON格式返回结果，并确保在返回的JSON中包含用户提供的原始漏洞信息。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
            }
            if max_tokens is not None:
                api_params["max_tokens"] = max_tokens

            response = await client.chat.completions.create(**api_params)
            content = response.choices[0].message.content

            debug_file = Path(__file__).parent.parent / "pocs" / "metadata" / debug_filename
            try:
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                logger.warning(f"保存调试响应失败: {e}")

            parsed_content = self._parse_llm_json_response(content, debug_file)
            logger.info("✅ JSON解析成功")
            logger.info("=" * 60)
            return parsed_content
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            if not error_msg.startswith("LLM返回了无效的JSON"):
                logger.error("=" * 60)
                logger.error(f"❌ API调用失败: {error_type}")
                if hasattr(e, 'response'):
                    logger.error(f"HTTP状态码: {getattr(e.response, 'status_code', 'N/A')}")
                logger.error("=" * 60)
            raise Exception(f"API调用失败: {error_msg}")


# 创建全局服务实例
llm_service = LLMService()
