import asyncio
import unittest
from pathlib import Path

from services.llm_service import LLMService


class LLMOOBPromptTests(unittest.TestCase):
    def setUp(self):
        self.service = LLMService()

    def test_prompt_template_mentions_oob_helper(self):
        prompt = self.service._build_prompt("目标存在无回显SSRF漏洞", None)
        self.assertIn("get_oob_client()", prompt)
        self.assertIn('verification_method="oob"', prompt)
        self.assertIn("SSRF、XXE、无回显RCE", prompt)
        self.assertIn("create_http_client()", prompt)
        self.assertIn("send_raw_http()", prompt)
        self.assertIn("不要吞掉异常", prompt)
        self.assertIn('execution_mode="url_with_params"', prompt)
        self.assertIn("input_schema", prompt)
        self.assertIn("runtime_params", prompt)

    def test_fallback_prompt_mentions_oob_helper(self):
        self.service.prompt_config = {}
        prompt = self.service._build_prompt("目标存在无回显RCE漏洞", None)
        self.assertIn("get_oob_client()", prompt)
        self.assertIn("create_oob_client()", prompt)
        self.assertIn('"verification_method": "direct 或 oob"', prompt)
        self.assertIn("create_http_client()", prompt)
        self.assertIn("send_raw_http()", prompt)
        self.assertIn("不要吞掉异常", prompt)
        self.assertIn("url_with_params", prompt)
        self.assertIn("input_schema", prompt)
        self.assertIn("get_runtime_param()", prompt)

    def test_generate_initial_poc_preserves_oob_metadata(self):
        async def fake_call(prompt):
            return {
                "verifiable": True,
                "vulnerability_name": "测试 SSRF 外带验证",
                "vulnerability_type": "SSRF",
                "original_vulnerability_info": "无回显SSRF",
                "execution_mode": "url_only",
                "verification_method": "oob",
                "input_schema": None,
                "poc_code": "def scan(url):\n    return {'vulnerable': False, 'reason': 'ok', 'details': ''}",
                "explanation": "使用平台OOB helper进行验证",
            }

        self.service._call_llm_api = fake_call
        result = asyncio.run(self.service.generate_initial_poc("目标存在无回显SSRF漏洞"))

        self.assertTrue(result["verifiable"])
        self.assertEqual(result["execution_mode"], "url_only")
        self.assertEqual(result["verification_method"], "oob")
        self.assertIsNone(result["input_schema"])

    def test_generate_initial_poc_keeps_direct_metadata_when_not_oob(self):
        async def fake_call(prompt):
            return {
                "verifiable": True,
                "vulnerability_name": "测试 直连验证",
                "vulnerability_type": "SQL注入",
                "original_vulnerability_info": "有回显SQL注入",
                "execution_mode": "url_only",
                "verification_method": "direct",
                "input_schema": None,
                "poc_code": "def scan(url):\n    client = create_http_client()\n    return {'vulnerable': False, 'reason': 'ok', 'details': ''}",
                "explanation": "使用平台HTTP helper完成直连验证",
            }

        self.service._call_llm_api = fake_call
        result = asyncio.run(self.service.generate_initial_poc("目标存在回显SQL注入漏洞"))

        self.assertTrue(result["verifiable"])
        self.assertEqual(result["execution_mode"], "url_only")
        self.assertEqual(result["verification_method"], "direct")

    def test_parse_llm_json_response_restores_literal_newlines_in_poc_code(self):
        raw = (
            '{"verifiable": true, "vulnerability_name": "Demo", "vulnerability_type": "read", '
            '"original_vulnerability_info": "demo", "execution_mode": "url_only", '
            '"verification_method": "direct", "input_schema": null, '
            '"poc_code": "import requests\\\\n\\\\ndef scan(url):\\\\n    return {\\"vulnerable\\": false, \\"reason\\": \\"ok\\", \\"details\\": \\"\\"}", '
            '"explanation": "demo"}'
        )

        parsed = self.service._parse_llm_json_response(raw, Path("dummy.json"))
        self.assertIn("\n\ndef scan(url):\n", parsed["poc_code"])
        self.assertNotIn("\\n", parsed["poc_code"])

    def test_review_prompt_emphasizes_preserving_strong_trigger_points(self):
        prompt = self.service._build_review_prompt(
            "Apache Solr 存在 Log4j2 JNDI 注入",
            "目标暴露 /solr/admin/cores 接口",
            "SHOULD_NOT_BE_INCLUDED_IN_REVIEW_PROMPT",
            {
                "verifiable": True,
                "vulnerability_name": "Demo",
                "vulnerability_type": "RCE",
                "original_vulnerability_info": "demo",
                "execution_mode": "url_only",
                "verification_method": "oob",
                "input_schema": None,
                "poc_code": "def scan(url):\n    return {}",
                "explanation": "demo",
            },
        )

        self.assertIn("最小必要修改", prompt)
        self.assertIn("高置信触发点", prompt)
        self.assertIn("不要把已存在的参数注入、路径注入、接口参数注入方案", prompt)
        self.assertIn("不要在 client.verify() 外再额外手写长轮询", prompt)
        self.assertNotIn("SHOULD_NOT_BE_INCLUDED_IN_REVIEW_PROMPT", prompt)


if __name__ == "__main__":
    unittest.main()
