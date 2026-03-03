#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from openai import OpenAI

DEFAULT_BASE_URL = "https://api.aicodewith.com/chatgpt/v1"
DEFAULT_MODEL = "gpt-5.2"

CACHE_PATH = Path(__file__).resolve().parent.parent / ".cache" / "translations.json"
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_api_key() -> str | None:
    for k in ("OPENAI_API_KEY", "AICODEWITH_API_KEY"):
        v = os.environ.get(k)
        if v:
            return v

    try:
        cfg_path = Path("~/.openclaw/openclaw.json").expanduser()
        if cfg_path.exists():
            obj = json.loads(cfg_path.read_text(encoding="utf-8"))
            providers = (((obj.get("models") or {}).get("providers")) or {})
            p = providers.get("aicodewith-gpt") or {}
            v = p.get("apiKey")
            if isinstance(v, str) and v:
                return v
    except Exception:
        pass

    return None


def translate_zh(
    text: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    cache = _load_cache()
    k = _key(text)
    if k in cache:
        return cache[k]

    base_url = base_url or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL
    api_key = api_key or _resolve_api_key()
    model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL

    if not api_key:
        raise RuntimeError("Missing API key. Set OPENAI_API_KEY (or AICODEWITH_API_KEY).")

    client = OpenAI(base_url=base_url, api_key=api_key)

    prompt = (
        "将下面的英文财经资讯摘要翻译成简体中文，要求：\n"
        "- 不要添加原文没有的信息\n"
        "- 保留公司名/股票代码/缩写（如 NVDA、FOMC、CPI）\n"
        "- 句子短一些，适合早报阅读\n"
        "- 如果原文已经是中文就原样返回\n\n"
        f"正文：\n{text}"
    )

    last_err: Exception | None = None
    for attempt in range(4):
        try:
            resp = client.responses.create(
                model=model,
                input=prompt,
                max_output_tokens=280,
            )
            out = (resp.output_text or "").strip()
            cache[k] = out
            _save_cache(cache)
            time.sleep(0.15)
            return out
        except Exception as e:
            last_err = e
            time.sleep(0.8 * (attempt + 1))

    raise RuntimeError(f"translate failed after retries: {last_err}")


if __name__ == "__main__":
    import sys

    src = sys.stdin.read() if not sys.argv[1:] else " ".join(sys.argv[1:])
    print(translate_zh(src))
