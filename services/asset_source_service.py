"""
空间测绘目标导入服务

支持：
1. FOFA
2. Hunter
3. Quake
"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_ASSET_CONFIG = {
    "fofa": {
        "email": None,
        "token": None,
        "base_url": "https://fofa.info/api/v1",
    },
    "hunter": {
        "token": None,
        "base_url": "https://hunter.qianxin.com/openApi/search",
    },
    "quake": {
        "token": None,
        "base_url": "https://quake.360.net/api/v3",
    },
}


def _mask_secret(value: Optional[str]) -> str:
    if not value:
        return "未设置"
    if len(value) <= 6:
        return f"{value[:2]}***"
    return f"{value[:3]}...{value[-3:]}"


def _mask_email(value: Optional[str]) -> str:
    if not value:
        return "未设置"
    if "@" not in value:
        return _mask_secret(value)
    name, domain = value.split("@", 1)
    if len(name) <= 2:
        return f"{name[:1]}***@{domain}"
    return f"{name[:2]}***@{domain}"


class FofaClient:
    def __init__(
        self,
        email: str,
        token: str,
        base_url: str,
        session: Optional[requests.Session] = None,
        sleep_func: Optional[Callable[[float], None]] = None,
    ):
        if not email or not token:
            raise RuntimeError("FOFA 邮箱或 Token 未配置")
        self.email = email
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.sleep_func = sleep_func or time.sleep

    def search(self, query: str, pages: int = 1) -> List[str]:
        qbase64 = base64.b64encode(query.encode("utf-8")).decode("utf-8")
        results = []
        seen = set()
        for page in range(1, max(pages, 1) + 1):
            url = (
                f"{self.base_url}/search/all?email={self.email}&key={self.token}"
                f"&qbase64={qbase64}&fields=protocol,host&page={page}"
            )
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            payload = response.json()
            for row in payload.get("results", []):
                protocol = row[0] or "http"
                host = row[1]
                target = host if "://" in host else f"{protocol}://{host}"
                if target not in seen:
                    seen.add(target)
                    results.append(target)
            self.sleep_func(0)
        return results


class HunterClient:
    def __init__(
        self,
        token: str,
        base_url: str,
        session: Optional[requests.Session] = None,
        sleep_func: Optional[Callable[[float], None]] = None,
    ):
        if not token:
            raise RuntimeError("Hunter Token 未配置")
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.sleep_func = sleep_func or time.sleep

    def search(self, query: str, pages: int = 1) -> List[str]:
        encoded = base64.urlsafe_b64encode(query.encode("utf-8")).decode("utf-8")
        results = []
        seen = set()
        for page in range(1, max(pages, 1) + 1):
            url = (
                f"{self.base_url}?api-key={self.token}&search={encoded}"
                f"&page={page}&page_size=20&is_web=3"
            )
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            payload = response.json()
            for item in (payload.get("data") or {}).get("arr", []):
                target = item.get("url")
                if target and target not in seen:
                    seen.add(target)
                    results.append(target)
            self.sleep_func(0)
        return results


class QuakeClient:
    def __init__(
        self,
        token: str,
        base_url: str,
        session: Optional[requests.Session] = None,
        sleep_func: Optional[Callable[[float], None]] = None,
    ):
        if not token:
            raise RuntimeError("Quake Token 未配置")
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.sleep_func = sleep_func or time.sleep

    def search(self, query: str, pages: int = 1) -> List[str]:
        results = []
        seen = set()
        headers = {
            "Content-Type": "application/json",
            "X-QuakeToken": self.token,
        }
        for page in range(1, max(pages, 1) + 1):
            payload = {"query": query, "size": 10, "ignore_cache": "false", "start": page}
            response = self.session.post(f"{self.base_url}/search/quake_service", json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            for item in data.get("data", []):
                ip = item.get("ip")
                port = item.get("port")
                if not ip or not port:
                    continue
                target = f"http://{ip}:{port}"
                if target not in seen:
                    seen.add(target)
                    results.append(target)
            self.sleep_func(0)
        return results


class AssetSourceService:
    def __init__(
        self,
        config_file: Optional[Path] = None,
        provider_factories: Optional[Dict[str, Callable[[], object]]] = None,
    ):
        self.base_dir = Path(__file__).parent.parent
        self.config_file = config_file or (self.base_dir / "pocs" / "asset_source_config.json")
        self.config = self._load_config()
        self.provider_factories = provider_factories or {
            "fofa": self._create_fofa_client,
            "hunter": self._create_hunter_client,
            "quake": self._create_quake_client,
        }

    def _load_config(self) -> Dict[str, Dict[str, Optional[str]]]:
        config = json.loads(json.dumps(DEFAULT_ASSET_CONFIG))
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for provider, values in saved.items():
                    if provider in config and isinstance(values, dict):
                        config[provider].update(values)
            except Exception as exc:
                logger.error("加载空间测绘配置失败: %s", exc)
        return config

    def _save_config(self):
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def update_provider_config(
        self,
        provider: str,
        email: Optional[str] = None,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        provider = (provider or "").lower().strip()
        if provider not in self.config:
            raise ValueError(f"不支持的空间测绘平台: {provider}")

        if provider == "fofa":
            self.config["fofa"]["email"] = email or None
        if token is not None:
            self.config[provider]["token"] = token or None
        if base_url:
            self.config[provider]["base_url"] = base_url
        self._save_config()

    def get_current_config(self) -> Dict[str, Dict[str, str]]:
        return {
            "fofa": {
                "email_preview": _mask_email(self.config["fofa"].get("email")),
                "token_preview": _mask_secret(self.config["fofa"].get("token")),
                "base_url": self.config["fofa"].get("base_url"),
            },
            "hunter": {
                "token_preview": _mask_secret(self.config["hunter"].get("token")),
                "base_url": self.config["hunter"].get("base_url"),
            },
            "quake": {
                "token_preview": _mask_secret(self.config["quake"].get("token")),
                "base_url": self.config["quake"].get("base_url"),
            },
        }

    def import_targets(self, provider: str, query: str, pages: int = 1) -> Dict:
        provider = (provider or "").lower().strip()
        if provider not in self.provider_factories:
            raise ValueError(f"不支持的空间测绘平台: {provider}")
        if not query or not query.strip():
            raise ValueError("查询语句不能为空")

        client = self.provider_factories[provider]()
        targets = client.search(query.strip(), pages=max(int(pages or 1), 1))
        return {
            "provider": provider,
            "query": query.strip(),
            "pages": max(int(pages or 1), 1),
            "targets": targets,
            "total": len(targets),
        }

    def _create_fofa_client(self) -> FofaClient:
        conf = self.config["fofa"]
        return FofaClient(
            email=conf.get("email"),
            token=conf.get("token"),
            base_url=conf.get("base_url"),
        )

    def _create_hunter_client(self) -> HunterClient:
        conf = self.config["hunter"]
        return HunterClient(
            token=conf.get("token"),
            base_url=conf.get("base_url"),
        )

    def _create_quake_client(self) -> QuakeClient:
        conf = self.config["quake"]
        return QuakeClient(
            token=conf.get("token"),
            base_url=conf.get("base_url"),
        )


asset_source_service = AssetSourceService()
