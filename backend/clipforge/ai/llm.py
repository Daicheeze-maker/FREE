"""Optional vision/language model through a local OpenAI-compatible server.

Works with llama.cpp `llama-server` (Vulkan build for AMD GPUs), LM Studio and Ollama.
Nothing is sent anywhere unless the user enables it, and a non-local URL is refused
unless "allow cloud AI" is also switched on.
"""
from __future__ import annotations

import base64
import ipaddress
import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .. import settings
from ..errors import ModelError


def is_local_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host in ("localhost",):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return False


class LLMClient:
    def __init__(self, base_url: str, model: str, api_key: str = "", vision: bool = True, timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.vision = vision
        self.timeout = timeout

    def _post(self, path: str, body: dict | None) -> dict:
        req = urllib.request.Request(self.base_url + path, method="POST" if body is not None else "GET",
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            # Local servers must be reached directly, not through a system HTTP proxy.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if is_local_url(self.base_url) \
                else urllib.request.build_opener()
            with opener.open(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ModelError(f"The AI server returned HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ModelError(f"Could not reach the local AI server at {self.base_url} ({e}).") from e
        except ValueError as e:
            raise ModelError("The AI server sent a response that is not JSON.") from e

    def models(self) -> list[str]:
        return [m.get("id", "") for m in self._post("/models", None).get("data", [])]

    def chat(self, system: str, user: str, images: list[bytes] | None = None, max_tokens: int = 900) -> str:
        content: list | str = user
        if images:
            content = [{"type": "text", "text": user}] + [
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(i).decode()}}
                for i in images]
        body = {"model": self.model, "temperature": 0.2, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
        data = self._post("/chat/completions", body)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ModelError("The AI server response had no message content.") from e

    def chat_json(self, system: str, user: str, images: list[bytes] | None = None, max_tokens: int = 900):
        return extract_json(self.chat(system, user, images, max_tokens))


def extract_json(text: str):
    """Models wrap JSON in prose or code fences; pull out the first valid object/array."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    for m in re.finditer(r"[\[{]", text):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[m.start():])
            return obj
        except ValueError:
            continue
    raise ModelError("The AI model did not return valid JSON.")


def get_client() -> LLMClient | None:
    """Configured client, or None when the optional model is disabled."""
    cfg = settings.get_all(include_secrets=True)
    if not cfg["llm_enabled"] or not cfg["llm_base_url"]:
        return None
    if not is_local_url(cfg["llm_base_url"]) and not cfg["allow_cloud_ai"]:
        raise ModelError("The AI server address is not on this computer or local network. "
                         "Enable 'Allow cloud AI' in Settings > Privacy to use it.")
    return LLMClient(cfg["llm_base_url"], cfg["llm_model"], cfg["llm_api_key"] or "", bool(cfg["llm_vision"]))


def test_connection() -> dict:
    client = get_client()
    if client is None:
        return {"ok": False, "error": "The local AI model is disabled."}
    try:
        models = client.models()
        reply = client.chat("You are a test.", "Reply with the single word: ready", max_tokens=8)
        return {"ok": True, "models": models, "reply": reply.strip()[:80],
                "local": is_local_url(client.base_url)}
    except ModelError as e:
        return {"ok": False, "error": str(e)}
