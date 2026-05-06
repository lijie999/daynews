#!/usr/bin/env python3
"""
财经标题翻译器：使用 MyMemory（免费，1000字/5min）
缓存翻译结果到 .cache/translations.json
"""
import hashlib
import json
import time
from pathlib import Path
from typing import Optional

REPO_DIR = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_DIR / ".cache" / "translations.json"
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

_trans_cache: Optional[dict] = None


def _load_cache() -> dict:
    global _trans_cache
    if _trans_cache is not None:
        return _trans_cache
    if CACHE_PATH.exists():
        try:
            _trans_cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            return _trans_cache
        except Exception:
            pass
    _trans_cache = {}
    return _trans_cache


def _save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    global _trans_cache
    _trans_cache = cache


def _key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def translate_zh(text: str) -> str:
    """翻译英文标题到简体中文（带缓存）"""
    text = (text or "").strip()
    if not text:
        return ""
    if _is_likely_chinese(text):
        return text

    cache = _load_cache()
    k = _key(text)
    if k in cache:
        return cache[k]

    try:
        from deep_translator import MyMemoryTranslator
        result = MyMemoryTranslator(source="en-US", target="zh-CN").translate(text)
        if result and result != text:
            cache[k] = result
            _save_cache(cache)
            time.sleep(0.3)  # rate limit: 1000 chars / 5 min → ~100 chars/request
            return result
    except Exception:
        pass

    return text


def translate_batch(texts: list[str]) -> list[str]:
    """批量翻译（保留未能翻译的原文）"""
    results = []
    for t in texts:
        results.append(translate_zh(t))
    return results


def _is_likely_chinese(text: str) -> bool:
    """判断是否已经是中文（简单启发式）"""
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return chinese_chars / max(len(text), 1) > 0.3
