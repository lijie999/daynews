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
else:
    # Interactive runs may not have env vars; try to read from LaunchAgent like above.
    try:
        import plistlib

        p = Path("~/Library/LaunchAgents/ai.openclaw.daynews.update.plist").expanduser()
        if p.exists():
            obj = plistlib.loads(p.read_bytes())
            key = (obj.get("EnvironmentVariables") or {}).get("NVIDIA_API_KEY")
            if isinstance(key, str) and key and key != "REPLACE_ME":
                os.environ["NVIDIA_API_KEY"] = key
                from scripts.translate_nvidia import translate_zh  # type: ignore
    except Exception:
        pass

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
BRIEFS_PATH = REPO_DIR / "docs" / "briefs.json"

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


def _looks_english(s: str) -> bool:
    s = (s or "").strip()
    if not s:
        return False
    # Heuristic: if it contains a meaningful amount of ASCII letters, treat as English.
    letters = sum(1 for ch in s if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    return letters >= 12


def _render_item(it: dict[str, Any], *, translate: bool = False) -> str:
    src = (it.get("source") or "").replace("&", "&amp;")
    ticker = (it.get("related") or "").replace("&", "&amp;")
    tm = _ts_to_bjt(it.get("datetime"))

    raw_title = (it.get("headline") or it.get("title") or "").strip()
    raw_summ = (it.get("summary") or "").strip()

    if translate and translate_zh is not None:
        if raw_title and _looks_english(raw_title):
            try:
                raw_title = translate_zh(raw_title)
            except Exception:
                pass
        if raw_summ and _looks_english(raw_summ):
            try:
                raw_summ = translate_zh(raw_summ)
            except Exception:
                # Translation is best-effort; fall back silently.
                pass

    title = raw_title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    summ = raw_summ.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    url = (it.get("url") or "#").replace('"', "%22")

    if not title:
        title = "（标题缺失）"
    if not summ:
        summ = "（摘要缺失：来源未提供）"

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

    # Prefer RSS cache when available (more timely, broader coverage).
    rss_cache = REPO_DIR / ".cache" / "rss_items.json"
    if rss_cache.exists():
        try:
            obj = json.loads(rss_cache.read_text(encoding="utf-8"))
            all_items.extend(obj.get("items") or [])
        except Exception:
            pass

    # Fall back to cached Finnhub ticker news.
    if not all_items:
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
        """Generate a more systematic 'main thesis' block.

        Offline-friendly: we only use headline heuristics + the freshest items.
        Output is short, structured, and oriented to day-trading.
        """
        lines: list[str] = []

        risk = b.get("地缘/能源/避险") or []
        macro = b.get("美联储与政策") or []
        tech = b.get("七姐妹与半导体链") or []
        tsla_chain = b.get("特斯拉链") or []

        def head(items: list[dict[str, Any]]) -> str:
            if not items:
                return ""
            return str(items[0].get("headline") or "").strip()[:72]

        # 1) 主导因子（1-2个）
        drivers: list[str] = []
        if macro:
            drivers.append("10Y/利率")
        if risk:
            drivers.append("原油/风险事件")
        if tech or tsla_chain:
            drivers.append("权重/财报/监管")
        if not drivers:
            drivers = ["10Y/利率", "VIX/风险偏好"]
        drivers = drivers[:2]
        lines.append(f"主导因子：{drivers[0]}{(' + ' + drivers[1]) if len(drivers) > 1 else ''}")

        # 2) 四件套占位（无实时行情时，给监控要点）
        lines.append("四件套监控：10Y（方向/拐点）｜DXY（强弱）｜VIX（是否抬升）｜原油/风险事件（是否升级）")

        # 3) 跨资产联动（通用结论）
        lines.append("跨资产联动：10Y↑→NQ/ES承压更明显；DXY↑→GC更易回撤；VIX↑→盘中更易急拉急杀/假突破")

        # 4) 关键窗口（未来90分钟占位）
        lines.append("未来90分钟关键窗口：关注是否临近数据/讲话/美债拍卖/开盘等事件窗；事件前后避免追单")

        # 5) 两套情���（条件触发型；离线用通用触发）
        lines.append("情景A：若10Y继续上行且VIX抬升→偏NQ/ES先空后看、GC偏弱震荡；操作偏好：等确认后顺势")
        lines.append("情景B：若10Y回落且VIX回落→偏NQ/ES修复反弹、GC喘息；操作偏好：回踩参与、避免追高")

        # 6) 期权一句（通用）
        lines.append("期权：事件密度高→偏买波动/带保护；事件窗过去且VIX回落→再考虑卖波动")

        # 7) 本轮线索（引用最新标题，帮助快速定位）
        hints: list[str] = []
        if risk:
            hints.append(f"地缘/避险线索：{head(risk)}…")
        if macro:
            hints.append(f"宏观/Fed线索：{head(macro)}…")
        if tech:
            kw = _hot_words(tech, k=4)
            tag = ("关键词:" + ",".join(kw)) if kw else ""
            hints.append(f"科技/半导体线索：{head(tech)}… {tag}".strip())
        if tsla_chain:
            hints.append(f"TSLA线索：{head(tsla_chain)}…")
        if hints:
            lines.append("——")
            lines.extend(hints[:3])

        # keep within ~10 lines
        return lines[:10]

    lines = _summary_lines(buckets)
    buckets["主线结论"] = [
        {
            "headline": "主线结论（系统版｜条件触发）",
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
    .nav{{margin-top:12px}}
    .back{{display:inline-flex;align-items:center;gap:8px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);padding:8px 12px;border-radius:999px;font-family:var(--mono);font-size:12px;color:var(--muted);text-decoration:none}}
    .back:hover{{text-decoration:underline}}
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
      <div class=\"nav\"><a class=\"back\" href=\"./\">← 返回首页</a></div>
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

    # Write briefs.json for the redesigned homepage/list view.
    sections_meta = [
        ("主线结论", "Summary"),
        ("七姐妹与半导体链", "Mag7 / Semis"),
        ("美联储与政策", "Fed / Policy"),
        ("地缘/能源/避险", "Risk / Oil / Gold"),
        ("特斯拉链", "TSLA chain"),
        ("其他", "Other"),
    ]

    def _item_to_brief(it: dict[str, Any], *, translate: bool = False) -> dict[str, Any]:
        title = (it.get("headline") or it.get("title") or "").strip()
        summary = (it.get("summary") or "").strip()
        title_en = title
        summary_en = summary

        if translate and translate_zh is not None:
            if title and _looks_english(title):
                try:
                    title = translate_zh(title)
                except Exception:
                    title = title
            if summary and _looks_english(summary):
                try:
                    summary = translate_zh(summary)
                except Exception:
                    summary = summary

        out = {
            "source": it.get("source") or "",
            "ticker": it.get("related") or "",
            "time": _ts_to_bjt(it.get("datetime")),
            "title": title,
            "summary": summary,
            "url": it.get("url") or "#",
        }

        # Preserve original fields when we changed them.
        if title != title_en:
            out["title_en"] = title_en
        if summary != summary_en:
            out["summary_en"] = summary_en

        return out

    briefs_obj = {
        "date": now.strftime("%Y.%m.%d"),
        "generatedAtBJT": last_updated,
        "translation": {
            "enabled": bool(translate_zh is not None),
            "provider": "nvidia" if os.environ.get("NVIDIA_API_KEY") else ("openclaw" if os.environ.get("OPENCLAW_TRANSLATE") else "unknown"),
            "policy": "translate_if_english",
        },
        "sections": [],
    }

    # Translate every item that looks English (best-effort). This can be slow if many items.
    for name, badge in sections_meta:
        items = buckets.get(name) or []
        briefs_obj["sections"].append(
            {
                "name": name,
                "badge": badge,
                "items": [_item_to_brief(x, translate=True) for x in items],
            }
        )

    BRIEFS_PATH.write_text(
        json.dumps(briefs_obj, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
