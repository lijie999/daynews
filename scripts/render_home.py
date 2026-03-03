#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

REPO_DIR = Path("/Users/lijiaolong/.openclaw/workspace/daynews")
DOCS = REPO_DIR / "docs"
BRIEFS = DOCS / "briefs.json"
OUT = DOCS / "home.html"


def _now_bjt() -> dt.datetime:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))


def _load_briefs() -> dict:
    if not BRIEFS.exists():
        return {}
    try:
        return json.loads(BRIEFS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _history_files(limit: int = 14) -> list[str]:
    files = sorted(DOCS.glob("每日财经早报*.html"), reverse=True)
    out: list[str] = []
    for f in files:
        if f.name == "每日财经早报.html":
            continue
        out.append(f.name)
        if len(out) >= limit:
            break
    return out


def main() -> int:
    now = _now_bjt()
    data = _load_briefs()
    date = data.get("date") or now.strftime("%Y.%m.%d")
    generated = data.get("generatedAtBJT") or now.strftime("%Y-%m-%d %H:%M:%S")
    sections = data.get("sections") or []

    # Keep only the main four + optional other
    allow = {"主线结论", "七姐妹与半导体链", "美联储与政策", "地缘/能源/避险", "特斯拉链", "其他"}
    sections = [s for s in sections if (s.get("name") in allow)]

    history = _history_files()

    # Render sections from briefs.json (already translated where available)
    def esc(s: str) -> str:
        return (
            (s or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def sec_html(sec: dict) -> str:
        name = esc(sec.get("name") or "")
        badge = esc(sec.get("badge") or "")
        items = sec.get("items") or []
        body = []
        for it in items[:18]:
            title = esc(it.get("title") or "")
            summ = esc(it.get("summary") or "")
            tm = esc(it.get("time") or "")
            src = esc(it.get("source") or "")
            ticker = esc(it.get("ticker") or "")
            url = esc(it.get("url") or "#")
            if not title:
                continue
            body.append(
                "<div class=\"item\">"
                f"<div class=\"top\"><div class=\"src\">{src} · {ticker}</div><div class=\"time\">{tm}</div></div>"
                f"<a href=\"{url}\" target=\"_blank\" rel=\"noreferrer noopener\"><div class=\"title\">{title}</div></a>"
                f"<p class=\"meta\">{summ}</p>"
                "</div>"
            )
        if not body:
            body_html = '<div class="note">（暂无）</div>'
        else:
            body_html = "\n".join(body)

        return (
            '<section class="card">'
            f'<h2><span>{name}</span><span class="badge">{badge}</span></h2>'
            f'<div class="items">{body_html}</div>'
            '</section>'
        )

    hist_items = "\n".join(
        f'<a class="hitem" href="{esc(name)}"><div class="hdate">{esc(name.replace("每日财经早报", "").replace(".html", ""))}</div><div class="hgo">打开</div></a>'
        for name in history
    )

    page = f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>DayNews · {date}</title>
  <style>
    :root{{
      --bg0:#070b16; --bg1:#0b1020; --stroke: rgba(255,255,255,.12);
      --text:#f2f6ff; --muted: rgba(242,246,255,.72); --faint: rgba(242,246,255,.52);
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      --serif: ui-serif, "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
      --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      --r: 18px;
    }}
    body{{margin:0;color:var(--text);font-family:var(--sans);background:radial-gradient(1000px 600px at 12% -10%, rgba(72,108,255,.20), rgba(7,11,22,0) 60%),linear-gradient(180deg,var(--bg1),var(--bg0));}}
    .wrap{{max-width:1160px;margin:0 auto;padding:22px 18px 56px;display:grid;grid-template-columns: 1fr 320px;gap:16px;align-items:start}}
    @media (max-width: 980px){{.wrap{{grid-template-columns:1fr}} .side{{position:static !important; width:auto}}}}

    header{{border:1px solid var(--stroke);background:rgba(255,255,255,.06);border-radius:var(--r);padding:18px 16px;}}
    .k{{font-family:var(--mono);font-size:12px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap}}
    .pill{{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);padding:6px 10px;border-radius:999px}}
    h1{{margin:10px 0 6px;font-family:var(--serif);font-size: clamp(26px, 4.2vw, 46px);line-height:1.1}}
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

    .side{{position:sticky; top:16px}}
    .panel{{border:1px solid var(--stroke);background:rgba(255,255,255,.05);border-radius:var(--r);overflow:hidden}}
    .panel h3{{margin:0;padding:14px 14px 12px;border-bottom:1px solid rgba(255,255,255,.10);font-family:var(--mono);font-size:12px;color:var(--muted);letter-spacing:.03em;display:flex;justify-content:space-between;align-items:center}}
    .hlist{{padding:10px 10px 12px;display:flex;flex-direction:column;gap:8px}}
    .hitem{{border:1px solid rgba(255,255,255,.10);background:rgba(0,0,0,.12);border-radius:14px;padding:10px 10px;display:flex;justify-content:space-between;align-items:center;gap:10px}}
    .hdate{{font-family:var(--mono);font-size:12px;color:var(--text)}}
    .hgo{{font-family:var(--mono);font-size:12px;color:var(--muted)}}
    .navrow{{padding:10px 10px 12px;display:flex;gap:8px;flex-wrap:wrap}}
    .btn{{display:inline-flex;align-items:center;gap:8px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);padding:8px 12px;border-radius:999px;font-family:var(--mono);font-size:12px;color:var(--muted)}}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <main>
      <header>
        <div class=\"k\">
          <span class=\"pill\">当日 24h 快讯与分析</span>
          <span class=\"pill\">最后更新：{esc(generated)}（北京时间）</span>
          <span class=\"pill\">数据：briefs.json</span>
        </div>
        <h1>DayNews · {date}</h1>
        <p class=\"sub\">首页只展示近 24 小时的重点（以缓存源时间为准）。点击标题跳转原文；历史在右侧悬浮模块。</p>
      </header>

      {"\n".join(sec_html(s) for s in sections)}
    </main>

    <aside class=\"side\">
      <div class=\"panel\">
        <h3><span>历史</span><span class=\"badge\">{len(history)}</span></h3>
        <div class=\"navrow\">
          <a class=\"btn\" href=\"list.html\">列表</a>
          <a class=\"btn\" href=\"briefs.json\">JSON</a>
        </div>
        <div class=\"hlist\">{hist_items}</div>
      </div>
    </aside>
  </div>
</body>
</html>
"""

    OUT.write_text(page, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
