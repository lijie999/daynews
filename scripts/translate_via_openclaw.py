#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

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


def translate_zh(text: str, *, model: str = "gpt-5.2") -> str:
    text = (text or "").strip()
    if not text:
        return ""

    cache = _load_cache()
    k = _key(text)
    if k in cache:
        return cache[k]

    msg = (
        "你是财经早报翻译助手。把下面英文摘要翻译为简体中文，要求：\n"
        "- 不要添加原文没有的信息\n"
        "- 保留公司名/股票代码/缩写（NVDA、FOMC、CPI 等）\n"
        "- 句子短、信息密度高，适合列表阅读\n"
        "- 如果已是中文，原样返回\n\n"
        f"正文：\n{text}"
    )

    # Use gateway-routed agent turn, so it shares the same provider path that works for chat.
    cmd = [
        "openclaw",
        "agent",
        "--agent",
        "main",
        "--message",
        msg,
        "--json",
        "--timeout",
        "120",
    ]

    last_err: str | None = None
    for attempt in range(3):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0:
            try:
                obj = json.loads(p.stdout)
                # Best-effort output extraction.
                out = (obj.get("reply") or obj.get("message") or obj.get("text") or "").strip()
                if not out:
                    out = (obj.get("result") or "").strip() if isinstance(obj.get("result"), str) else ""
                if out:
                    cache[k] = out
                    _save_cache(cache)
                    time.sleep(0.15)
                    return out
                last_err = "empty output"
            except Exception as e:
                last_err = f"json parse failed: {e}"
        else:
            last_err = (p.stderr or p.stdout or "").strip()[-400:]

        time.sleep(0.8 * (attempt + 1))

    raise RuntimeError(f"translate via openclaw failed: {last_err}")


if __name__ == "__main__":
    src = sys.stdin.read() if not sys.argv[1:] else " ".join(sys.argv[1:])
    print(translate_zh(src))
