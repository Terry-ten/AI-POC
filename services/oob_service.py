"""
OOB 外带验证服务

功能：
1. 统一管理 Interactsh / CEye 配置
2. 为 POC 脚本提供统一的 OOB client
3. 统一返回命中/未命中/异常语义
"""

from __future__ import annotations

import base64
import importlib
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import uuid4

import requests

logger = logging.getLogger(__name__)

DEFAULT_OOB_CONFIG = {
    "enabled": False,
    "provider": "interactsh",
    "interactsh_server": "oast.me",
    "interactsh_token": None,
    "ceye_token": None,
    "ceye_base_url": "http://api.ceye.io/v1",
    "poll_interval": 1.0,
    "max_polls": 3,
}


class BaseOOBClient:
    """统一 OOB client 接口。"""

    def build_probe(self, protocol: str = "http", length: int = 10, value: str = "") -> Dict[str, str]:
        raise NotImplementedError

    def verify(self, flag: str, protocol: str = "http") -> Dict[str, object]:
        raise NotImplementedError


class CEyeClient(BaseOOBClient):
    def __init__(
        self,
        token: str,
        base_url: str = "http://api.ceye.io/v1",
        poll_interval: float = 1.0,
        max_polls: int = 3,
        session: Optional[requests.Session] = None,
        sleep_func: Optional[Callable[[float], None]] = None,
    ):
        if not token:
            raise RuntimeError("CEye token 未配置")

        self.token = token
        self.base_url = (base_url or "http://api.ceye.io/v1").rstrip("/")
        self.poll_interval = max(poll_interval or 1.0, 0)
        self.max_polls = max(int(max_polls or 3), 1)
        self.session = session or requests.Session()
        self.sleep_func = sleep_func or time.sleep
        self.identify = self._load_identify()

    def _load_identify(self) -> str:
        response = self.session.get(
            f"{self.base_url}/identify",
            headers={"Authorization": self.token, "User-Agent": "AI-POC/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        identify = payload.get("data", {}).get("identify")
        if not identify:
            raise RuntimeError("CEye identify 获取失败")
        return identify

    def build_probe(self, protocol: str = "http", length: int = 10, value: str = "") -> Dict[str, str]:
        flag = uuid4().hex[: max(length, 4)].lower()
        domain = f"{self.identify}.ceye.io"

        if protocol in ("request", "http"):
            sanitized_value = re.sub(r"\W", "", value or "")
            url = f"http://{flag}.{domain}/{flag}{sanitized_value}{flag}"
        elif protocol == "dns":
            sanitized_value = re.sub(r"\W", "", value or "")
            url = f"{flag}{sanitized_value}{flag}.{domain}"
        else:
            raise ValueError(f"不支持的CEye协议类型: {protocol}")

        return {"url": url, "flag": flag}

    def verify(self, flag: str, protocol: str = "http") -> Dict[str, object]:
        record_type = "dns" if protocol == "dns" else "request"
        query_url = f"{self.base_url}/records?token={self.token}&type={record_type}&filter={flag}"
        events: List[Dict[str, object]] = []

        for _ in range(self.max_polls):
            try:
                response = self.session.get(query_url, timeout=10)
                response.raise_for_status()
                payload = response.json()
                events = payload.get("data") or []
                if any(flag.lower() in json.dumps(item, ensure_ascii=False).lower() for item in events):
                    return {"matched": True, "events": events, "error": None}
            except Exception as exc:
                logger.warning("CEye 轮询失败: %s", exc)
                events = []
            self.sleep_func(self.poll_interval)

        return {"matched": False, "events": events, "error": None}


class InteractshClient(BaseOOBClient):
    def __init__(
        self,
        server: str = "oast.me",
        token: Optional[str] = None,
        poll_interval: float = 1.0,
        max_polls: int = 3,
        session: Optional[requests.Session] = None,
        sleep_func: Optional[Callable[[float], None]] = None,
    ):
        try:
            AES, PKCS1_OAEP, SHA256, RSA = load_interactsh_crypto_backend()
        except ImportError as exc:
            raise RuntimeError("Interactsh 需要安装 pycryptodome 或 pycryptodomex") from exc

        self._AES = AES
        self._PKCS1_OAEP = PKCS1_OAEP
        self._SHA256 = SHA256
        self._RSA = RSA

        rsa = RSA.generate(2048)
        self.public_key = rsa.publickey().exportKey()
        self.private_key = rsa.exportKey()

        self.server = (server or "oast.me").lstrip(".")
        self.token = token
        self.poll_interval = max(poll_interval or 1.0, 0)
        self.max_polls = max(int(max_polls or 3), 1)
        self.session = session or requests.Session()
        self.sleep_func = sleep_func or time.sleep

        self.headers = {"Content-Type": "application/json"}
        if self.token:
            self.headers["Authorization"] = self.token

        self.secret = str(uuid4())
        self.encoded = base64.b64encode(self.public_key).decode("utf8")
        guid = uuid4().hex.ljust(33, "a")
        guid = "".join(i if i.isdigit() else chr(ord(i) + random.randint(0, 20)) for i in guid)
        self.domain = f"{guid}.{self.server}"
        self.correlation_id = self.domain[:20]

        self._register()

    def _register(self):
        payload = {
            "public-key": self.encoded,
            "secret-key": self.secret,
            "correlation-id": self.correlation_id,
        }
        response = self.session.post(
            f"http://{self.server}/register",
            headers=self.headers,
            json=payload,
            timeout=10,
            verify=False,
        )
        response.raise_for_status()

    def build_probe(self, protocol: str = "http", length: int = 10, value: str = "") -> Dict[str, str]:
        flag = uuid4().hex[: max(length, 4)].lower()
        host = f"{flag}.{self.domain}"
        if protocol.startswith("http"):
            url = f"{protocol}://{host}"
        elif protocol == "dns":
            url = host
        else:
            raise ValueError(f"不支持的Interactsh协议类型: {protocol}")
        return {"url": url, "flag": flag}

    def _decrypt_data(self, aes_key: str, data: str) -> Dict[str, object]:
        private_key = self._RSA.importKey(self.private_key)
        cipher = self._PKCS1_OAEP.new(private_key, hashAlgo=self._SHA256)
        aes_plain_key = cipher.decrypt(base64.b64decode(aes_key))
        decoded = base64.b64decode(data)
        block_size = self._AES.block_size
        iv = decoded[:block_size]
        cryptor = self._AES.new(key=aes_plain_key, mode=self._AES.MODE_CFB, IV=iv, segment_size=128)
        plain_text = cryptor.decrypt(decoded)
        return json.loads(plain_text[16:])

    def verify(self, flag: str, protocol: str = "http") -> Dict[str, object]:
        events: List[Dict[str, object]] = []
        for _ in range(self.max_polls):
            try:
                poll_url = f"http://{self.server}/poll?id={self.correlation_id}&secret={self.secret}"
                response = self.session.get(poll_url, headers=self.headers, timeout=10, verify=False)
                response.raise_for_status()
                payload = response.json() or {}
                encrypted_items = payload.get("data") or []
                if not isinstance(encrypted_items, list):
                    encrypted_items = [encrypted_items] if encrypted_items else []

                aes_key = payload.get("aes_key")
                decrypted = []
                if aes_key and encrypted_items:
                    decrypted = [
                        self._decrypt_data(aes_key, item)
                        for item in encrypted_items
                        if item
                    ]
                events = decrypted
                if any(flag.lower() in json.dumps(item, ensure_ascii=False).lower() for item in decrypted):
                    return {"matched": True, "events": events, "error": None}
            except Exception as exc:
                logger.warning("Interactsh 轮询失败: %s", exc)
                events = []
            self.sleep_func(self.poll_interval)

        return {"matched": False, "events": events, "error": None}


def load_interactsh_crypto_backend():
    """兼容 Crypto / Cryptodome 两种命名空间。"""
    import_errors = []
    for namespace in ("Cryptodome", "Crypto"):
        try:
            aes_module = importlib.import_module(f"{namespace}.Cipher.AES")
            pkcs1_oaep_module = importlib.import_module(f"{namespace}.Cipher.PKCS1_OAEP")
            hash_module = importlib.import_module(f"{namespace}.Hash.SHA256")
            public_key_module = importlib.import_module(f"{namespace}.PublicKey.RSA")
            return (
                aes_module,
                pkcs1_oaep_module,
                hash_module,
                public_key_module,
            )
        except ImportError as exc:
            import_errors.append(f"{namespace}: {exc}")

    raise ImportError("; ".join(import_errors))


class OOBService:
    def __init__(
        self,
        config_file: Optional[Path] = None,
        provider_factories: Optional[Dict[str, Callable[..., BaseOOBClient]]] = None,
    ):
        self.base_dir = Path(__file__).parent.parent
        self.config_file = config_file or (self.base_dir / "pocs" / "oob_config.json")
        self.provider_factories = provider_factories or {
            "interactsh": self._create_interactsh_client,
            "ceye": self._create_ceye_client,
        }
        self.config = self._load_config_from_file()

    def _load_config_from_file(self) -> Dict[str, object]:
        config = dict(DEFAULT_OOB_CONFIG)
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                config.update({k: v for k, v in saved.items() if v is not None})
            except Exception as exc:
                logger.error("加载OOB配置失败: %s", exc)
        return config

    def _save_config_to_file(self):
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def update_config(
        self,
        enabled: bool,
        provider: str,
        interactsh_server: Optional[str] = None,
        interactsh_token: Optional[str] = None,
        ceye_token: Optional[str] = None,
        ceye_base_url: Optional[str] = None,
        poll_interval: float = 1.0,
        max_polls: int = 3,
    ):
        provider = (provider or "interactsh").lower().strip()
        if provider not in self.provider_factories:
            raise ValueError(f"不支持的 OOB 提供商: {provider}")

        self.config.update(
            {
                "enabled": bool(enabled),
                "provider": provider,
                "interactsh_server": interactsh_server or DEFAULT_OOB_CONFIG["interactsh_server"],
                "interactsh_token": interactsh_token or None,
                "ceye_token": ceye_token or None,
                "ceye_base_url": ceye_base_url or DEFAULT_OOB_CONFIG["ceye_base_url"],
                "poll_interval": max(float(poll_interval or 1.0), 0),
                "max_polls": max(int(max_polls or 3), 1),
            }
        )
        self._save_config_to_file()

    def get_current_config(self) -> Dict[str, object]:
        runtime_status = self.get_runtime_status()

        return {
            "enabled": bool(self.config.get("enabled")),
            "provider": self.config.get("provider"),
            "interactsh_server": self.config.get("interactsh_server"),
            "interactsh_token_preview": self._preview_secret(self.config.get("interactsh_token")),
            "ceye_base_url": self.config.get("ceye_base_url"),
            "ceye_token_preview": self._preview_secret(self.config.get("ceye_token")),
            "poll_interval": self.config.get("poll_interval"),
            "max_polls": self.config.get("max_polls"),
            "dependency_ready": runtime_status["dependency_ready"],
            "dependency_error": runtime_status["dependency_error"],
            "runtime_ready": runtime_status["runtime_ready"],
            "runtime_error": runtime_status["runtime_error"],
        }

    def _preview_secret(self, value: Optional[str]) -> str:
        if not value:
            return "未设置"
        if len(value) <= 6:
            return f"{value[:2]}***"
        return f"{value[:3]}...{value[-3:]}"

    def _create_ceye_client(self) -> BaseOOBClient:
        return CEyeClient(
            token=self.config.get("ceye_token"),
            base_url=self.config.get("ceye_base_url"),
            poll_interval=self.config.get("poll_interval", 1.0),
            max_polls=self.config.get("max_polls", 3),
        )

    def _create_interactsh_client(self) -> BaseOOBClient:
        return InteractshClient(
            server=self.config.get("interactsh_server"),
            token=self.config.get("interactsh_token"),
            poll_interval=self.config.get("poll_interval", 1.0),
            max_polls=self.config.get("max_polls", 3),
        )

    def get_runtime_status(self, provider: Optional[str] = None) -> Dict[str, object]:
        resolved_provider = (provider or self.config.get("provider") or "interactsh").lower()
        enabled = bool(self.config.get("enabled"))
        dependency_ready = True
        dependency_error = None
        runtime_ready = enabled
        runtime_error = None

        if not enabled:
            runtime_ready = False
            runtime_error = "OOB 验证未启用"

        if resolved_provider == "interactsh":
            try:
                load_interactsh_crypto_backend()
            except ImportError:
                dependency_ready = False
                dependency_error = "Interactsh 依赖未安装，请安装 pycryptodome 或 pycryptodomex"
        elif resolved_provider == "ceye":
            if not self.config.get("ceye_token"):
                runtime_ready = False
                runtime_error = "CEye token 未配置"

        if enabled and not dependency_ready:
            runtime_ready = False
            runtime_error = dependency_error

        return {
            "enabled": enabled,
            "provider": resolved_provider,
            "dependency_ready": dependency_ready,
            "dependency_error": dependency_error,
            "runtime_ready": runtime_ready,
            "runtime_error": runtime_error,
        }

    def ensure_runtime_ready(self, provider: Optional[str] = None):
        status = self.get_runtime_status(provider=provider)
        if not status["runtime_ready"]:
            raise RuntimeError(status["runtime_error"] or "OOB 运行环境不可用")
        return status

    def create_client(self, provider: Optional[str] = None) -> BaseOOBClient:
        resolved_provider = (provider or self.config.get("provider") or "interactsh").lower()
        self.ensure_runtime_ready(provider=resolved_provider)
        factory = self.provider_factories.get(resolved_provider)
        if not factory:
            raise RuntimeError(f"不支持的 OOB 提供商: {resolved_provider}")
        return factory()


oob_service = OOBService()
