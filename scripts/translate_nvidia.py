#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent.parent / ".cache" / "translations.json"
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")


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


def translate_zh(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    cache = _load_cache()
    k = _key(text)
    if k in cache:
        return cache[k]

    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("Missing NVIDIA_API_KEY")

    url = BASE_URL.rstrip("/") + "/chat/completions"
    body = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是财经早报翻译助手。把用户提供的英文摘要翻译为简体中文。"
                    "要求：不添加原文没有的信息；保留公司名/股票代码/缩写（NVDA、FOMC、CPI、S&P 500等）；"
                    "句子短、信息密度高；如果已是中文，原样返回。只输出译文。"
                ),
            },
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "max_tokens": 280,
    }

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    last_err: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                obj = json.loads(raw)
                out = obj["choices"][0]["message"]["content"].strip()
                cache[k] = out
                _save_cache(cache)
                time.sleep(0.15)
                return out
        except Exception as e:
            last_err = e
            time.sleep(0.8 * (attempt + 1))

    raise RuntimeError(f"nvidia translate failed: {last_err}")
