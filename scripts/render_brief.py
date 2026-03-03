#!/usr/bin/env python3
"""Render DayNews briefing HTML.

This is intentionally deterministic and offline-friendly:
- Uses cached Finnhub JSON files when present.
- Optionally enriches with Tavily search results if TAVILY_API_KEY is set.

Output:
- docs/每日财经早报YYYY.MM.DD.html

Note: This script does NOT try to be a full translation engine.
It produces Chinese summaries by using available Finnhub summaries and
lightweight templating. If a summary is English, it is left as-is for now.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

# Optional translation. Prefer NVIDIA (free) if NVIDIA_API_KEY is present.
translate_zh = None  # type: ignore

# If running under launchd, env vars may not be visible in interactive runs.
# Best-effort: read NVIDIA_API_KEY from the LaunchAgent plist so local renders match scheduler behavior.
if not os.environ.get("NVIDIA_API_KEY"):
    try:
        import plistlib

        p = Path("~/Library/LaunchAgents/ai.openclaw.daynews.update.plist").expanduser()
        if p.exists():
            obj = plistlib.loads(p.read_bytes())
            key = (obj.get("EnvironmentVariables") or {}).get("NVIDIA_API_KEY")
            if isinstance(key, str) and key and key != "REPLACE_ME":
                os.environ["NVIDIA_API_KEY"] = key
    except Exception:
        pass

if os.environ.get("NVIDIA_API_KEY"):
    try:
        from scripts.translate_nvidia import translate_zh  # type: ignore
    except Exception:
        translate_zh = None  # type: ignore

if translate_zh is None:
    try:
        from scripts.translate_via_openclaw import translate_zh  # type: ignore
    except Exception:  # pragma: no cover
        try:
            from scripts.translate import translate_zh  # type: ignore
        except Exception:  # pragma: no cover
            translate_zh = None  # type: ignore

REPO_DIR = Path("/Users/lijiaolong/.openclaw/workspace/daynews")
CACHE_DIR = Path("/Users/lijiaolong/.openclaw/workspace/daily-brief")
OUT_PATH = REPO_DIR / "docs" / f"每日财经早报{dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime('%Y.%m.%d')}.html"

TICKERS = [
    "spy",
    "qqq",
    "aapl",
    "msft",
    "amzn",
    "meta",
    "googl",
    "tsla",
    "nvda",
    "avgo",
    "amd",
    "mrvl",
    "asml",
    "tsm",
]


def _now_bjt() -> dt.datetime:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))


def _load_json(path: Path) -> list[dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for it in sorted(items, key=lambda x: int(x.get("datetime") or 0), reverse=True):
        k = str(it.get("url") or it.get("id") or it.get("headline") or "")
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def _ts_to_bjt(ts: Any) -> str:
    try:
        ts_i = int(ts)
    except Exception:
        return ""
    d = dt.datetime.fromtimestamp(ts_i, tz=dt.timezone.utc).astimezone(
        dt.timezone(dt.timedelta(hours=8))
    )
    return d.strftime("%Y-%m-%d %H:%M:%S")


def _bucket(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    geo = re.compile(r"\b(Iran|Israel|Israeli|UAE|missile|Doha|Qatar|Abu Dhabi|strike|blasts?|oil|OPEC|Hormuz|Gaza)\b", re.I)
    macro = re.compile(r"\b(Fed|FOMC|inflation|PPI|CPI|Payroll|Non-?Farm|NFP|jobs|yield|rates|Treasury)\b", re.I)
    ai = re.compile(r"\b(AI|NVIDIA|NVDA|GPU|chip|semiconductor|data center|cloud|OpenAI|Microsoft|Google|Meta|Amazon|Apple)\b", re.I)
    tsla = re.compile(r"\b(Tesla|TSLA|robotaxi|Cybercab|Optimus|autonomous|self-driving|robot)\b", re.I)

    b: dict[str, list[dict[str, Any]]] = {
        "主线结论": [],
        "七姐妹与半导体链": [],
        "美联储与政策": [],
        "地缘/能源/避险": [],
        "特斯拉链": [],
        "其他": [],
    }

    for it in items:
        h = it.get("headline") or ""
        if geo.search(h):
            b["地缘/能源/避险"].append(it)
        elif macro.search(h):
            b["美联储与政策"].append(it)
        elif tsla.search(h):
            b["特斯拉链"].append(it)
        elif ai.search(h):
            b["七姐妹与半导体链"].append(it)
        else:
            b["其他"].append(it)

    # Trim for readability
    for k in ("七姐妹与半导体链", "美联储与政策", "地缘/能源/避险", "特斯拉链", "其他"):
        b[k] = b[k][:18]

    return b


def _render_item(it: dict[str, Any], *, translate: bool = False) -> str:
    src = (it.get("source") or "").replace("&", "&amp;")
    ticker = (it.get("related") or "").replace("&", "&amp;")
    tm = _ts_to_bjt(it.get("datetime"))
    title = (it.get("headline") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    raw_summ = (it.get("summary") or "").strip()
    if translate and translate_zh is not None and raw_summ:
        try:
            raw_summ = translate_zh(raw_summ)
        except Exception:
            # Translation is best-effort; fall back silently.
            pass

    summ = raw_summ.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    url = (it.get("url") or "#").replace('"', "%22")

    if not summ:
        summ = "（摘要缺失：来源未提供）"

    # Allow multi-line summary; render as <br> for readability.
    summ_html = summ.replace("\n", "<br>")

    return (
        '<div class="item">'
        f'<div class="top"><div class="src">{src} · {ticker}</div><div class="time">{tm}</div></div>'
        f'<a href="{url}" target="_blank" rel="noreferrer noopener"><div class="title">{title}</div></a>'
        f'<p class="meta">{summ_html}</p>'
        "</div>"
    )


def main() -> int:
    all_items: list[dict[str, Any]] = []
    for t in TICKERS:
        p = CACHE_DIR / f"{t}_et.json"
        if not p.exists():
            continue
        all_items.extend(_load_json(p))

    ded = _dedupe(all_items)
    buckets = _bucket(ded)

    now = _now_bjt()
    last_updated = now.strftime("%Y-%m-%d %H:%M:%S")
    hms = now.strftime("%H:%M:%S")

    def _hot_words(items: list[dict[str, Any]], k: int = 6) -> list[str]:
        # Cheap keywording for headlines; avoids heavy NLP deps.
        stop = {
            "the","a","an","and","or","to","of","in","on","for","with","as","at","from",
            "by","after","before","into","over","under","will","is","are","was","were","be",
            "this","that","these","those","it","its","they","their","you","your","we","our",
            "stock","stocks","market","markets","says","said","report","reports","earnings",
        }
        freq: dict[str, int] = {}
        for it in items:
            h = str(it.get("headline") or "")
            for w in re.findall(r"[A-Za-z]{3,}", h):
                wl = w.lower()
                if wl in stop:
                    continue
                freq[wl] = freq.get(wl, 0) + 1
        # Prefer repeated words; then alphabetical for determinism.
        top = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
        return [w for w, _n in top[:k]]

    def _summary_lines(b: dict[str, list[dict[str, Any]]]) -> list[str]:
        # Pull a few signals from the freshest items in each bucket.
        lines: list[str] = []

        risk = b.get("地缘/能源/避险") or []
        if risk:
            lines.append(f"地缘/避险：关注 {risk[0].get('headline','').strip()[:64]}…")

        macro = b.get("美联储与政策") or []
        if macro:
            lines.append(f"宏观/Fed：关注 {macro[0].get('headline','').strip()[:64]}…")

        tech = b.get("七姐妹与半导体链") or []
        if tech:
            # Add a light keyword tag to avoid a generic sentence.
            kw = _hot_words(tech, k=5)
            tag = ("关键词: " + ", ".join(kw)) if kw else ""
            head = str(tech[0].get("headline") or "").strip()[:64]
            lines.append(f"科技/半导体：{head}…{(' ' + tag) if tag else ''}")

        tsla_chain = b.get("特斯拉链") or []
        if tsla_chain:
            lines.append(f"TSLA：关注 {tsla_chain[0].get('headline','').strip()[:64]}…")

        # Keep it tight.
        return lines[:5]

    lines = _summary_lines(buckets)
    if not lines:
        lines = ["今日暂无明显主线（样本较少/来源暂无更新），以下为分板块快讯。"]

    buckets["主线结论"] = [
        {
            "headline": "主线结论（自动生成）",
            "summary": "\n".join(f"- {ln}" for ln in lines),
            "source": "DayNews",
            "related": "SUMMARY",
            "datetime": int(now.timestamp()),
            "url": "#",
        }
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    def sec(name: str, badge: str, items: list[dict[str, Any]]) -> str:
        # Translate only the first N items per section to control cost/latency.
        N_TRANSLATE = 8
        if not items:
            body = '<div class="note">（暂无）</div>'
        else:
            chunks: list[str] = []
            for i, it in enumerate(items):
                chunks.append(_render_item(it, translate=(i < N_TRANSLATE)))
            body = "\n".join(chunks)
        return (
            '<section class="card">'
            f'<h2><span>{name}</span><span class="badge">{badge}</span></h2>'
            f'<div class="items">{body}</div>'
            '</section>'
        )

    page = f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>每日财经早报{now.strftime('%Y.%m.%d')} · 更新 {hms}</title>
  <style>
    :root{{
      --bg0:#070b16; --bg1:#0b1020; --stroke: rgba(255,255,255,.12);
      --text:#f2f6ff; --muted: rgba(242,246,255,.72); --faint: rgba(242,246,255,.52);
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      --serif: ui-serif, "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
      --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      --r: 18px;
    }}
    body{{margin:0;color:var(--text);font-family:var(--sans);background:linear-gradient(180deg,var(--bg1),var(--bg0));}}
    .wrap{{max-width:1100px;margin:0 auto;padding:26px 18px 56px}}
    header{{border:1px solid var(--stroke);background:rgba(255,255,255,.06);border-radius:var(--r);padding:20px 18px;}}
    .k{{font-family:var(--mono);font-size:12px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap}}
    .pill{{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);padding:6px 10px;border-radius:999px}}
    h1{{margin:10px 0 6px;font-family:var(--serif);font-size: clamp(26px, 4.2vw, 44px);line-height:1.1}}
    .sub{{margin:0;color:var(--muted);line-height:1.6;max-width:90ch;font-size:14.5px}}
    .card{{margin-top:14px;border:1px solid var(--stroke);background:rgba(255,255,255,.05);border-radius:var(--r);overflow:hidden}}
    .card h2{{margin:0;padding:14px 14px 12px;border-bottom:1px solid rgba(255,255,255,.10);font-family:var(--mono);font-size:12px;color:var(--muted);letter-spacing:.03em;display:flex;justify-content:space-between;align-items:center}}
    .badge{{font-family:var(--mono);font-size:11px;padding:6px 10px;border:1px solid rgba(255,255,255,.14);border-radius:999px;background:rgba(255,255,255,.05);color:var(--muted)}}
    .items{{padding:12px 14px 16px;display:flex;flex-direction:column;gap:10px}}
    .item{{border:1px solid rgba(255,255,255,.10);background:rgba(0,0,0,.12);border-radius:16px;padding:10px 10px}}
    .top{{display:flex;justify-content:space-between;gap:10px;align-items:baseline}}
    .src{{font-family:var(--mono);font-size:11px;color:var(--faint)}}
    .time{{font-family:var(--mono);font-size:11px;color:var(--muted)}}
    .title{{margin:6px 0 6px;font-size:14px;font-weight:780;line-height:1.25}}
    .meta{{margin:0;color:var(--muted);font-size:12.5px;line-height:1.45}}
    .note{{font-family:var(--mono);font-size:12px;color:var(--muted);line-height:1.55}}
    a{{color:inherit;text-decoration:none}} a:hover{{text-decoration:underline}}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <header>
      <div class=\"k\">
        <span class=\"pill\">口径：美东时间</span>
        <span class=\"pill\">最后更新：{last_updated}（北京时间）</span>
        <span class=\"pill\">来源：Finnhub（ticker news 缓存）</span>
      </div>
      <h1>每日财经早报{now.strftime('%Y.%m.%d')}</h1>
      <p class=\"sub\">自动生成版本：主线结论 → 七姐妹/半导体 → 美联储/政策 → 地缘/避险 → 特斯拉链。规则：同URL去重，按时间倒序；每个板块最多18条。</p>
    </header>

    {sec('主线结论','Summary',buckets['主线结论'])}
    {sec('七姐妹与半导体链','Mag7 / Semis',buckets['七姐妹与半导体链'])}
    {sec('美联储与政策','Fed / Policy',buckets['美联储与政策'])}
    {sec('地缘/能源/避险','Risk / Oil / Gold',buckets['地缘/能源/避险'])}
    {sec('特斯拉链','TSLA chain',buckets['特斯拉链'])}
  </div>
</body>
</html>
"""

    OUT_PATH.write_text(page, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
