import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import api.routes as routes_module
from main import app
from services.llm_service import LLMService


class SecondReviewFlowTests(unittest.TestCase):
    def test_update_review_config_persists_and_masks_secret(self):
        service = LLMService()
        with tempfile.TemporaryDirectory() as temp_dir:
            service.review_config_file = Path(temp_dir) / "review_llm.json"
            service.update_review_config(
                api_key="sk-review-1234567890",
                model_id="review-model",
                base_url="https://review.example/v1",
                temperature=0.2,
                max_tokens=2048,
            )

            current = service.get_current_review_config()
            self.assertEqual(current["model_id"], "review-model")
            self.assertEqual(current["base_url"], "https://review.example/v1")
            self.assertEqual(current["api_key_preview"], "sk-revi...7890")

    def test_review_generated_poc_uses_review_model_config(self):
        service = LLMService()
        service.review_api_key = "sk-review"
        service.review_api_base = "https://review.example/v1"
        service.review_model = "review-model"
        service.review_temperature = 0.2
        service.review_max_tokens = 1024

        captured = {}

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return {
                "verifiable": True,
                "vulnerability_name": "Reviewed Demo",
                "vulnerability_type": "SQL注入",
                "original_vulnerability_info": "demo",
                "execution_mode": "url_only",
                "verification_method": "direct",
                "input_schema": None,
                "poc_code": "def scan(url):\n    return {'vulnerable': False, 'reason': 'ok', 'details': ''}",
                "explanation": "reviewed",
            }

        service._call_llm_api_with_settings = fake_call

        result = asyncio.run(service.review_generated_poc(
            vulnerability_info="demo vuln",
            target_info=None,
            initial_prompt="INITIAL PROMPT",
            initial_result={
                "verifiable": True,
                "vulnerability_name": "Initial Demo",
                "vulnerability_type": "SQL注入",
                "original_vulnerability_info": "demo",
                "execution_mode": "url_only",
                "verification_method": "direct",
                "input_schema": None,
                "poc_code": "def scan(url):\n    return {'vulnerable': False, 'reason': 'init', 'details': ''}",
                "explanation": "initial",
            },
        ))

        self.assertEqual(result["vulnerability_name"], "Reviewed Demo")
        self.assertEqual(captured["model"], "review-model")
        self.assertEqual(captured["base_url"], "https://review.example/v1")
        self.assertEqual(captured["api_key"], "sk-review")
        self.assertIn("INITIAL PROMPT", captured["prompt"])

    def test_generate_route_applies_second_review_when_enabled(self):
        initial_result = {
            "verifiable": True,
            "vulnerability_name": "Initial Demo",
            "vulnerability_type": "SQL注入",
            "original_vulnerability_info": "demo",
            "execution_mode": "url_only",
            "verification_method": "direct",
            "input_schema": None,
            "poc_code": "def scan(url):\n    return {'vulnerable': False, 'reason': 'init', 'details': ''}",
            "explanation": "initial",
        }
        reviewed_result = {
            "verifiable": True,
            "vulnerability_name": "Reviewed Demo",
            "vulnerability_type": "SQL注入",
            "original_vulnerability_info": "demo",
            "execution_mode": "url_only",
            "verification_method": "direct",
            "input_schema": None,
            "poc_code": "def scan(url):\n    return {'vulnerable': False, 'reason': 'reviewed', 'details': ''}",
            "explanation": "reviewed",
        }

        with patch.object(routes_module.llm_service, "generate_initial_poc", AsyncMock(return_value=initial_result)) as generate_mock, \
             patch.object(routes_module.llm_service, "review_generated_poc", AsyncMock(return_value=reviewed_result)) as review_mock, \
             patch.object(routes_module.llm_service, "_build_prompt", return_value="INITIAL PROMPT"), \
             patch.object(routes_module.poc_library_service, "save_poc", return_value=1001):
            routes_module.llm_service.review_model = "review-model"
            client = TestClient(app)
            try:
                response = client.post("/api/generate-poc", json={
                    "vulnerability_info": "demo vulnerability",
                    "enable_second_review": True,
                })
            finally:
                client.close()

        self.assertEqual(response.status_code, 200)
        self.assertIn('"review_applied": true', response.text)
        self.assertIn('Reviewed Demo', response.text)
        generate_mock.assert_awaited_once()
        review_mock.assert_awaited_once()

    def test_generate_route_keeps_initial_result_when_second_review_fails(self):
        initial_result = {
            "verifiable": True,
            "vulnerability_name": "Initial Demo",
            "vulnerability_type": "SQL注入",
            "original_vulnerability_info": "demo",
            "execution_mode": "url_only",
            "verification_method": "direct",
            "input_schema": None,
            "poc_code": "def scan(url):\n    return {'vulnerable': False, 'reason': 'init', 'details': ''}",
            "explanation": "initial",
        }

        with patch.object(routes_module.llm_service, "generate_initial_poc", AsyncMock(return_value=initial_result)), \
             patch.object(routes_module.llm_service, "review_generated_poc", AsyncMock(side_effect=Exception("review failed"))), \
             patch.object(routes_module.llm_service, "_build_prompt", return_value="INITIAL PROMPT"), \
             patch.object(routes_module.poc_library_service, "save_poc", return_value=1002):
            routes_module.llm_service.review_model = "review-model"
            client = TestClient(app)
            try:
                response = client.post("/api/generate-poc", json={
                    "vulnerability_info": "demo vulnerability",
                    "enable_second_review": True,
                })
            finally:
                client.close()

        self.assertEqual(response.status_code, 200)
        self.assertIn('"review_applied": false', response.text)
        self.assertIn('"review_error": "review failed"', response.text)
        self.assertIn('Initial Demo', response.text)


if __name__ == "__main__":
    unittest.main()
