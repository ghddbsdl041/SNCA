"""mindlogic 게이트웨이 (OpenAI 호환 Chat Completions) 클라이언트.

SPEC.md 1번 항목의 API 설정을 그대로 따른다.
"""
import os
import time
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv
from langsmith import traceable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

with open(PROJECT_ROOT / "config" / "models.yaml", "r", encoding="utf-8") as f:
    MODELS_CONFIG = yaml.safe_load(f)

_API = MODELS_CONFIG["api"]
_BASE_URL = _API["base_url"]
_ENDPOINT = _API["endpoint"]
_API_KEY = os.environ[_API["api_key_env_var"]]

_HEADERS = {
    _API["auth_header"]: f"{_API['auth_scheme']} {_API_KEY}",
    "Content-Type": "application/json",
}


@traceable(name="gateway_chat_completion", run_type="llm")
def chat_completion(model_id: str, system_prompt: str, user_prompt: str, max_tokens: int,
                     temperature: float = 0.0, max_retries: int = 3, timeout: float = 120.0) -> dict:
    """단일 chat completion 호출. content와 finish_reason을 반환한다.

    LangSmith 추적: LANGSMITH_TRACING=true가 .env에 설정된 경우에만 실제로 전송되며,
    설정되지 않으면 @traceable은 아무 동작도 하지 않는다 (no-op).
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_exc = None
    for attempt in range(max_retries):
        try:
            resp = httpx.post(f"{_BASE_URL}{_ENDPOINT}", headers=_HEADERS, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            return {
                "content": choice["message"]["content"],
                "finish_reason": choice.get("finish_reason"),
                "raw": data,
            }
        except Exception as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"chat_completion failed after {max_retries} attempts: {last_exc}")
