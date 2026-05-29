# -*- coding: utf-8 -*-
"""多模型统一调用：OpenAI 兼容端点、Anthropic Claude、Google Gemini。"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from dotenv import load_dotenv

load_dotenv()

# 连通性检测：快速失败，避免登录长时间卡住
_VERIFY_TIMEOUT = httpx.Timeout(connect=12.0, read=22.0, write=15.0, pool=8.0)
# 正文生成：更长 read
_CHAT_TIMEOUT = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=15.0)

_OPENAI_CLIENTS: Dict[Tuple[str, str, str], Any] = {}
_ANTHROPIC_CLIENTS: Dict[Tuple[str, str], Any] = {}


def _proxy_url() -> Optional[str]:
    return (os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or "").strip() or None


def _is_mimo_endpoint(base: str) -> bool:
    return "xiaomimimo.com" in (base or "").lower()


def _require_ascii_api_key(key: str) -> str:
    """HTTP 头仅支持 ASCII；中文占位符会导致 httpx 报 ascii codec 错误。"""
    k = (key or "").strip()
    if not k:
        raise RuntimeError("API Key 为空")
    if "请替换" in k:
        raise RuntimeError("API Key 仍为占位符，请在 .env 填入小米平台申请的真实密钥后重启应用。")
    try:
        k.encode("ascii")
    except UnicodeEncodeError:
        raise RuntimeError("API Key 含非英文字符，请检查是否误粘贴了中文说明或全角符号。")
    return k


def _openai_compat_auth_headers(key: str, base: str) -> Dict[str, str]:
    k = _require_ascii_api_key(key)
    headers: Dict[str, str] = {"Authorization": f"Bearer {k}"}
    if _is_mimo_endpoint(base):
        headers["api-key"] = k
    return headers


def _normalize_base_url(base: str) -> str:
    """规范 OpenAI 兼容 base_url，避免重复 /v1 或缺少路径。"""
    b = (base or "https://api.openai.com/v1").strip().rstrip("/")
    if not b:
        return "https://api.openai.com/v1"
    # DeepSeek / 小米 MiMo 官方两种写法均可用；统一为带 /v1，与 OpenAI SDK 默认行为一致
    for host in ("api.deepseek.com", "api.xiaomimimo.com", "token-plan-cn.xiaomimimo.com"):
        if host in b and not b.endswith("/v1"):
            if b.endswith("/v1/chat/completions"):
                b = b.split("/v1/chat")[0] + "/v1"
            elif not b.endswith("/v1"):
                b = b + "/v1"
            break
    return b


def _httpx_client(timeout: httpx.Timeout) -> httpx.Client:
    proxy = _proxy_url()
    kwargs: Dict[str, Any] = {"timeout": timeout}
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.Client(**kwargs)


def _openai_client(cfg: Dict[str, Any], *, profile: str = "chat"):
    from openai import OpenAI

    base = _normalize_base_url(cfg.get("base_url") or "https://api.openai.com/v1")
    key = _require_ascii_api_key(cfg.get("api_key") or "")
    timeout = _VERIFY_TIMEOUT if profile == "verify" else _CHAT_TIMEOUT
    cache_key = (key, base, profile)
    if cache_key not in _OPENAI_CLIENTS:
        default_headers = {"api-key": key} if _is_mimo_endpoint(base) else None
        _OPENAI_CLIENTS[cache_key] = OpenAI(
            api_key=key,
            base_url=base,
            timeout=timeout,
            max_retries=0,
            default_headers=default_headers,
            http_client=_httpx_client(timeout),
        )
    return _OPENAI_CLIENTS[cache_key]


def _anthropic_client(cfg: Dict[str, Any], *, profile: str = "chat"):
    import anthropic

    key = (cfg.get("api_key") or "").strip()
    timeout = 90.0 if profile == "verify" else 300.0
    cache_key = (key, profile)
    if cache_key not in _ANTHROPIC_CLIENTS:
        proxy = _proxy_url()
        kwargs: Dict[str, Any] = {"api_key": key, "timeout": timeout, "max_retries": 0}
        if proxy:
            kwargs["http_client"] = httpx.Client(proxy=proxy, timeout=timeout)
        _ANTHROPIC_CLIENTS[cache_key] = anthropic.Anthropic(**kwargs)
    return _ANTHROPIC_CLIENTS[cache_key]


def _is_retryable_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    needles = (
        "timeout",
        "timed out",
        "connection",
        "connect",
        "reset",
        "503",
        "502",
        "504",
        "429",
        "rate",
        "temporarily",
    )
    return any(n in msg for n in needles)


def _with_retry(fn, *, attempts: int = 2, pause_s: float = 1.5):
    last: Optional[BaseException] = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if i >= attempts - 1 or not _is_retryable_error(e):
                raise
            msg = str(e).lower()
            wait = pause_s * (i + 1)
            if "429" in msg or "rate" in msg or "too many" in msg:
                wait = max(wait, 5.0 * (i + 1))
            time.sleep(wait)
    if last:
        raise last
    raise RuntimeError("retry failed")


def complete_chat(
    cfg: Dict[str, Any],
    system: str,
    user: str,
    *,
    temperature: float = 0.8,
    max_tokens: int = 4096,
    retry_attempts: int = 4,
    retry_pause: float = 2.0,
) -> str:
    """根据 cfg["provider"] 分发。"""
    prov = (cfg.get("provider") or "openai_compat").strip()
    key = _require_ascii_api_key(cfg.get("api_key") or "")

    def _call() -> str:
        if prov == "openai_compat":
            model = (cfg.get("model") or "gpt-4o-mini").strip()
            client = _openai_client(cfg, profile="chat")
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return (resp.choices[0].message.content or "").strip()

        if prov == "anthropic":
            model = (cfg.get("model") or "claude-sonnet-4-20250514").strip()
            client = _anthropic_client(cfg, profile="chat")
            msg = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                temperature=temperature,
            )
            parts = []
            for b in msg.content:
                if hasattr(b, "text"):
                    parts.append(b.text)
            return "".join(parts).strip()

        if prov == "gemini":
            import google.generativeai as genai

            genai.configure(api_key=key)
            model_name = (cfg.get("model") or "gemini-1.5-flash").strip()
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system,
            )
            resp = model.generate_content(
                user,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            try:
                return (resp.text or "").strip()
            except Exception:  # noqa: BLE001
                if resp.candidates:
                    parts = resp.candidates[0].content.parts
                    return "".join(getattr(p, "text", "") for p in parts).strip()
                return ""

        raise ValueError(f"未知 provider: {prov}")

    return _with_retry(_call, attempts=retry_attempts, pause_s=retry_pause)


def _verify_mimo_http(cfg: Dict[str, Any]) -> None:
    """小米 MiMo：用最小 chat/completions 探测（官方示例使用 api-key 头）。"""
    base = _normalize_base_url(cfg.get("base_url") or "https://api.xiaomimimo.com/v1")
    key = cfg.get("api_key") or ""
    model = (cfg.get("model") or os.getenv("LLM_MODEL") or "mimo-v2-flash").strip()
    url = f"{base.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    with httpx.Client(timeout=_VERIFY_TIMEOUT, proxy=_proxy_url()) as client:
        resp = client.post(
            url,
            headers={**_openai_compat_auth_headers(key, base), "Content-Type": "application/json"},
            json=payload,
        )
    if resp.status_code == 401:
        raise RuntimeError("API Key 无效或已过期（401）")
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {(resp.text or '')[:200]}")
    return


def _verify_openai_compat_http(cfg: Dict[str, Any]) -> None:
    """直接 HTTP 探测；小米 MiMo 走 chat/completions，其余走 /models。"""
    base = _normalize_base_url(cfg.get("base_url") or "https://api.openai.com/v1")
    if _is_mimo_endpoint(base):
        _verify_mimo_http(cfg)
        return
    key = cfg.get("api_key") or ""
    url = f"{base.rstrip('/')}/models"
    with httpx.Client(timeout=_VERIFY_TIMEOUT, proxy=_proxy_url()) as client:
        resp = client.get(url, headers=_openai_compat_auth_headers(key, base))
    if resp.status_code == 401:
        raise RuntimeError("API Key 无效或已过期（401）")
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {(resp.text or '')[:200]}")
    return


def verify_connection(cfg: Dict[str, Any]) -> tuple[bool, str]:
    """轻量连通性检测：OpenAI 兼容走 HTTP /models，其余走最小请求。"""
    prov = (cfg.get("provider") or "openai_compat").strip()
    try:
        _require_ascii_api_key(cfg.get("api_key") or "")
    except RuntimeError as e:
        return False, str(e)

    def _probe() -> None:
        if prov == "openai_compat":
            _verify_openai_compat_http(cfg)
            return
        if prov == "anthropic":
            client = _anthropic_client(cfg, profile="verify")
            client.messages.create(
                model=(cfg.get("model") or "claude-sonnet-4-20250514").strip(),
                max_tokens=8,
                messages=[{"role": "user", "content": "ping"}],
            )
            return
        if prov == "gemini":
            complete_chat(cfg, "Reply OK only.", "ping", temperature=0, max_tokens=8)
            return
        raise ValueError(f"未知 provider: {prov}")

    try:
        _with_retry(_probe, attempts=1, pause_s=0.0)
        return True, ""
    except Exception as e:  # noqa: BLE001
        err = str(e).strip() or type(e).__name__
        hint = ""
        if "timeout" in err.lower() or "timed out" in err.lower():
            base = (cfg.get("base_url") or "").lower()
            curl_host = "https://api.xiaomimimo.com" if "xiaomimimo.com" in base else "https://api.deepseek.com"
            hint = (
                "（提示：可点「跳过检测并进入」先使用；若需检测，请设置 HTTPS_PROXY 环境变量，"
                f"或在终端执行 curl {curl_host} 排查网络。）"
            )
        return False, f"{err}{hint}"


def cfg_from_preset(
    preset: str, api_key: str, custom_base: str = "", custom_model: str = ""
) -> Dict[str, Any]:
    """预设名称 -> 初始 cfg（用户可改 base/model）。"""
    p = preset.strip()
    if p == "小米 MiMo":
        env_base = os.getenv("OPENAI_BASE_URL", "https://api.xiaomimimo.com/v1").strip()
        return {
            "provider": "openai_compat",
            "api_key": api_key,
            "base_url": _normalize_base_url(env_base or "https://api.xiaomimimo.com/v1"),
            "model": custom_model or os.getenv("LLM_MODEL", "mimo-v2-flash"),
        }
    if p == "DeepSeek Chat":
        env_base = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com").strip()
        return {
            "provider": "openai_compat",
            "api_key": api_key,
            "base_url": _normalize_base_url(env_base or "https://api.deepseek.com"),
            "model": custom_model or os.getenv("LLM_MODEL", "deepseek-chat"),
        }
    if p == "OpenAI":
        return {
            "provider": "openai_compat",
            "api_key": api_key,
            "base_url": _normalize_base_url(custom_base or "https://api.openai.com/v1"),
            "model": custom_model or "gpt-4o-mini",
        }
    if p == "Claude (Anthropic)":
        return {
            "provider": "anthropic",
            "api_key": api_key,
            "base_url": "",
            "model": custom_model or "claude-sonnet-4-20250514",
        }
    if p == "Gemini (Google)":
        return {
            "provider": "gemini",
            "api_key": api_key,
            "base_url": "",
            "model": custom_model or "gemini-1.5-flash",
        }
  # 自定义 OpenAI 兼容网关
    return {
        "provider": "openai_compat",
        "api_key": api_key,
        "base_url": _normalize_base_url(custom_base or "https://api.openai.com/v1"),
        "model": custom_model or "gpt-4o-mini",
    }


def _valid_env_api_key(raw: str) -> str:
    k = (raw or "").strip()
    if not k or "请替换" in k:
        return ""
    try:
        k.encode("ascii")
    except UnicodeEncodeError:
        return ""
    return k


def default_api_key_from_env() -> str:
    """从环境变量读取默认密钥（优先 MIMO_API_KEY，其次 OPENAI_API_KEY）。"""
    for name in ("MIMO_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        k = _valid_env_api_key(os.getenv(name) or "")
        if k:
            return k
    return ""


def default_preset_from_env() -> str:
    """根据 .env 中的端点或专用变量推断登录页默认模型服务。"""
    base = (os.getenv("OPENAI_BASE_URL") or "").lower()
    if os.getenv("MIMO_API_KEY") or "xiaomimimo.com" in base:
        return "小米 MiMo"
    return "DeepSeek Chat"


def env_llm_defaults() -> tuple[str, str]:
    """未登录时从环境变量解析 base_url 与 model（供 llm_client 使用）。"""
    base = (os.getenv("OPENAI_BASE_URL") or "").strip()
    model = (os.getenv("LLM_MODEL") or "").strip()
    if not base:
        base = (
            "https://api.xiaomimimo.com/v1"
            if os.getenv("MIMO_API_KEY")
            else "https://api.deepseek.com"
        )
    if not model:
        model = "mimo-v2-flash" if "xiaomimimo.com" in base.lower() else "deepseek-chat"
    return _normalize_base_url(base), model
