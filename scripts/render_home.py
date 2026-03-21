#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

REPO_DIR = Path("/Users/lijiaolong/.openclaw/workspace/daynews")
DOCS = REPO_DIR / "docs"
BRIEFS = DOCS / "briefs.json"
OUT = DOCS / "index.html"


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

    # Keep only known sections
    allow = {"主线结论", "七姐妹与半导体链", "美联储与政策", "地缘/能源/避险", "特斯拉链", "其他"}
    sections = [s for s in sections if (s.get("name") in allow)]

    # Index by name
    sec_by = {str(s.get("name")): s for s in sections if s.get("name")}

    history = _history_files()

    def esc(s: str) -> str:
        return (
            (s or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def pick_items(*names: str) -> list[dict]:
        out: list[dict] = []
        for n in names:
            out.extend((sec_by.get(n) or {}).get("items") or [])
        return out

    def _badge_for(it: dict) -> str:
        # Severity tagging based on keywords (trade-desk heuristic).
        t = ((it.get("title") or "") + " " + (it.get("summary") or "")).lower()
        hot = any(
            k in t
            for k in [
                "fomc",
                "cpi",
                "ppi",
                "nfp",
                "payroll",
                "fed",
                "powell",
                "rate",
                "rates",
                "yield",
                "treasury",
                "auction",
                "opec",
                "iran",
                "israel",
                "missile",
                "strike",
                "sanction",
                "ceasefire",
            ]
        )
        warm = any(
            k in t
            for k in [
                "earnings",
                "guidance",
                "sec",
                "doj",
                "lawsuit",
                "ban",
                "tariff",
                "antitrust",
            ]
        )
        if hot:
            return "S"
        if warm:
            return "A"
        return "B"

    def _short_impact(it: dict) -> str:
        txt = ((it.get("title") or "") + " " + (it.get("summary") or "")).lower()
        impact: list[str] = []
        if any(k in txt for k in ["nasdaq", "s&p", "stocks", "equity", "chip", "nvidia", "apple", "microsoft", "tesla", "semiconductor"]):
            impact.append("NQ/ES")
        if any(k in txt for k in ["gold", "xau", "bullion"]):
            impact.append("GC")
        if any(k in txt for k in ["yield", "treasury", "bond", "rates", "10-year", "2-year", "auction"]):
            impact.append("利率")
        if any(k in txt for k in ["dollar", "dxy", "usd", "fx"]):
            impact.append("美元")
        if any(k in txt for k in ["vix", "volatility", "options", "0dte"]):
            impact.append("VIX/期权")
        if not impact:
            impact.append("综合")
        seen: set[str] = set()
        impact = [x for x in impact if not (x in seen or seen.add(x))]
        return "/".join(impact[:3])

    def _t(it: dict) -> str:
        return esc(it.get("time") or "")

    def render_thesis() -> str:
        sec = sec_by.get("主线结论") or {}
        items = sec.get("items") or []
        if not items:
            return '<section class="hero"><div class="note">（暂无主线结论）</div></section>'
        it = items[0]
        title = esc(it.get("title") or "主线结论")
        tm = esc(it.get("time") or "")
        summ = esc(it.get("summary") or "").replace("\n", "<br>")
        return (
            '<section class="hero">'
            '<div class="hero-top">'
            f'<div class="hero-title">{title}</div>'
            f'<div class="hero-time">{tm}</div>'
            '</div>'
            f'<div class="hero-body">{summ}</div>'
            '</section>'
        )

    def render_radar() -> str:
        pool = pick_items("美联储与政策", "地缘/能源/避险", "七姐妹与半导体链", "特斯拉链")
        seen: set[str] = set()
        uniq: list[dict] = []
        for it in pool:
            k = (it.get("url") or "") + "|" + (it.get("title") or "")
            if not k.strip() or k in seen:
                continue
            seen.add(k)
            uniq.append(it)

        def score(it: dict) -> int:
            b = _badge_for(it)
            return 200 if b == "S" else (100 if b == "A" else 0)

        uniq.sort(key=lambda it: (score(it), _t(it)), reverse=True)

        def row(it: dict) -> str:
            b = _badge_for(it)
            title = esc(it.get("title") or "")
            url = esc(it.get("url") or "#")
            tm = _t(it)
            impact = esc(_short_impact(it))
            summ = esc(it.get("summary") or "").replace("\n", " ")
            if len(summ) > 120:
                summ = summ[:120] + "…"
            return (
                '<div class="ritem">'
                f'<div class="rbadge r{b}">{b}</div>'
                '<div class="rmain">'
                f'<div class="rline"><span class="rtime">{tm}</span><span class="rimpact">{impact}</span></div>'
                f'<a class="rtitle" href="{url}" target="_blank" rel="noreferrer noopener">{title}</a>'
                f'<div class="rsumm">{summ}</div>'
                '</div>'
                '</div>'
            )

        s_list = [it for it in uniq if _badge_for(it) == "S"][:10]
        a_list = [it for it in uniq if _badge_for(it) == "A"][:10]

        def block(name: str, items: list[dict]) -> str:
            if not items:
                body = '<div class="note">（暂无）</div>'
            else:
                body = "\n".join(row(it) for it in items)
            return (
                '<section class="card">'
                f'<h2><span>{esc(name)}</span><span class="badge">{len(items)}</span></h2>'
                f'<div class="radar">{body}</div>'
                '</section>'
            )

        return block("事件雷达｜S级", s_list) + block("事件雷达｜A级", a_list)

    def render_zone(name: str, badge: str, items: list[dict]) -> str:
        seen: set[str] = set()
        uniq: list[dict] = []
        for it in items:
            k = (it.get("url") or "") + "|" + (it.get("title") or "")
            if not k.strip() or k in seen:
                continue
            seen.add(k)
            uniq.append(it)

        rows: list[str] = []
        for it in uniq[:18]:
            title = esc(it.get("title") or "")
            url = esc(it.get("url") or "#")
            tm = _t(it)
            src = esc(it.get("source") or "")
            ticker = esc(it.get("ticker") or "")
            rows.append(
                '<div class="titem">'
                f'<div class="tmeta"><span class="ttime">{tm}</span><span class="tsrc">{src} · {ticker}</span></div>'
                f'<a class="ttitle" href="{url}" target="_blank" rel="noreferrer noopener">{title}</a>'
                '</div>'
            )
        body = "\n".join(rows) if rows else '<div class="note">（暂无）</div>'
        return (
            '<section class="card">'
            f'<h2><span>{esc(name)}</span><span class="badge">{esc(badge)}</span></h2>'
            f'<div class="tlist">{body}</div>'
            '</section>'
        )

    # Trade-desk zones (best-effort mapping from existing sections)
    #
    # 去重与分类原则：
    # - 指数(Index)：聚焦“宏观/利率/大盘方向/风险偏好”相关线索
    # - 期权(Options)：聚焦“波动率/VIX/期权市场行为(0DTE/put-call/IV等)”相关线索
    # - 其它行业/个股（如七姐妹、特斯拉链）不要无脑灌进指数/期权，避免两栏内容形同。

    def _is_options(it: dict) -> bool:
        t = ((it.get("title") or "") + " " + (it.get("summary") or "")).lower()
        return any(
            k in t
            for k in [
                "options",
                "option",
                "0dte",
                "0-dte",
                "vix",
                "volatility",
                "implied volatility",
                "iv ",
                "gamma",
                "delta",
                "vega",
                "theta",
                "put",
                "call",
                "put/call",
                "put call",
            ]
        )

    def _is_index(it: dict) -> bool:
        t = ((it.get("title") or "") + " " + (it.get("summary") or "")).lower()
        # 这里的 index 主要指“大盘指数/指数期货/股指方向”，不把普通“index fund/ETF指数基金”也全部算进来
        return any(
            k in t
            for k in [
                "nasdaq",
                "s&p",
                "sp 500",
                "dow",
                "dow jones",
                "futures",
                "指数",
                "股指",
                "期货",
                "nq",
                "es",
                "ndx",
                "spx",
            ]
        ) or any(
            k in t
            for k in [
                "yield",
                "treasury",
                "bond",
                "rates",
                "rate",
                "10-year",
                "2-year",
                "fed",
                "fomc",
                "cpi",
                "ppi",
                "nfp",
                "payroll",
            ]
        )

    def _dedup(items: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        for it in items:
            k = (it.get("url") or "") + "|" + (it.get("title") or "")
            if not k.strip() or k in seen:
                continue
            seen.add(k)
            out.append(it)
        return out

    pool_macro = pick_items("美联储与政策", "地缘/能源/避险")
    pool_equity = pick_items("七姐妹与半导体链", "特斯拉链")

    # 1) 期权栏：先从宏观/风险事件里抓“波动/期权/VIX”相关，再补充少量个股链中明确提到 options 的条目
    zone_options = [it for it in _dedup(pool_macro + pool_equity) if _is_options(it)]

    # 2) 指数栏：偏宏观/利率 + 明确提到股指/期货的新闻；同时排除已归入期权栏的条目
    zone_index = [it for it in _dedup(pool_macro + pool_equity) if (_is_index(it) and (not _is_options(it)))]

    # 3) 黄金栏：保留原先逻辑（风险事件+宏观），避免被指数/期权污染
    zone_gold = pick_items("地缘/能源/避险", "美联储与政策")

    def sec_html(sec: dict) -> str:
        # Legacy raw view (compact)
        name = esc(sec.get("name") or "")
        badge = esc(sec.get("badge") or "")
        items = sec.get("items") or []
        rows: list[str] = []
        for it in items[:18]:
            title = esc(it.get("title") or "")
            tm = _t(it)
            src = esc(it.get("source") or "")
            ticker = esc(it.get("ticker") or "")
            url = esc(it.get("url") or "#")
            if not title:
                continue
            rows.append(
                '<div class="titem">'
                f'<div class="tmeta"><span class="ttime">{tm}</span><span class="tsrc">{src} · {ticker}</span></div>'
                f'<a class="ttitle" href="{url}" target="_blank" rel="noreferrer noopener">{title}</a>'
                '</div>'
            )
        body_html = "\n".join(rows) if rows else '<div class="note">（暂无）</div>'
        return (
            '<section class="card">'
            f'<h2><span>{name}</span><span class="badge">{badge}</span></h2>'
            f'<div class="tlist">{body_html}</div>'
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
      --S:#ff4d4d; --A:#ffb020; --B:#8b95a7;
      --fs-body: 15px;
      --fs-small: 12.5px;
      --fs-title: 15.5px;
    }}
    body{{margin:0;color:var(--text);font-family:var(--sans);font-size:var(--fs-body);background:radial-gradient(1000px 600px at 12% -10%, rgba(72,108,255,.20), rgba(7,11,22,0) 60%),linear-gradient(180deg,var(--bg1),var(--bg0));}}
    .wrap{{max-width:1480px;margin:0 auto;padding:22px 18px 56px;display:grid;grid-template-columns: 1fr 360px;gap:16px;align-items:start}}
    @media (max-width: 980px){{.wrap{{grid-template-columns:1fr}} .side{{position:static !important; width:auto}}}}

    header{{border:1px solid var(--stroke);background:rgba(255,255,255,.06);border-radius:var(--r);padding:18px 16px;}}
    .k{{font-family:var(--mono);font-size:12px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap}}
    .pill{{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);padding:6px 10px;border-radius:999px}}
    h1{{margin:10px 0 6px;font-family:var(--serif);font-size: clamp(26px, 4.2vw, 46px);line-height:1.1}}
    .sub{{margin:0;color:var(--muted);line-height:1.6;max-width:90ch;font-size:14.5px}}

    /* HERO (主线结论) */
    .hero{{margin-top:14px;border:1px solid rgba(255,255,255,.16);background:linear-gradient(180deg,rgba(255,255,255,.10),rgba(255,255,255,.05));border-radius:var(--r);padding:14px 14px 16px;}}
    .hero-top{{display:flex;justify-content:space-between;gap:10px;align-items:baseline;flex-wrap:wrap}}
    .hero-title{{font-family:var(--serif);font-size:22px;font-weight:850;}}
    .hero-time{{font-family:var(--mono);font-size:12px;color:var(--muted)}}
    .hero-body{{margin-top:10px;color:var(--text);font-size:15.5px;line-height:1.6}}

    .card{{margin-top:14px;border:1px solid var(--stroke);background:rgba(255,255,255,.05);border-radius:var(--r);overflow:hidden}}
    .card h2{{margin:0;padding:14px 14px 12px;border-bottom:1px solid rgba(255,255,255,.10);font-family:var(--mono);font-size:12px;color:var(--muted);letter-spacing:.03em;display:flex;justify-content:space-between;align-items:center}}
    .badge{{font-family:var(--mono);font-size:11px;padding:6px 10px;border:1px solid rgba(255,255,255,.14);border-radius:999px;background:rgba(255,255,255,.05);color:var(--muted)}}

    /* RADAR */
    .radar{{padding:12px 14px 16px;display:flex;flex-direction:column;gap:10px}}
    .ritem{{display:grid;grid-template-columns: 34px 1fr;gap:10px;border:1px solid rgba(255,255,255,.10);background:rgba(0,0,0,.12);border-radius:16px;padding:10px 10px}}
    .rbadge{{font-family:var(--mono);font-weight:900;font-size:12px;display:flex;align-items:center;justify-content:center;border-radius:12px;border:1px solid rgba(255,255,255,.18);height:34px;}}
    .rS{{background:rgba(255,77,77,.18);color:#ffd7d7;border-color:rgba(255,77,77,.35)}}
    .rA{{background:rgba(255,176,32,.18);color:#ffe7b6;border-color:rgba(255,176,32,.35)}}
    .rB{{background:rgba(139,149,167,.12);color:#d6dbe6;border-color:rgba(139,149,167,.25)}}
    .rline{{display:flex;gap:10px;align-items:center}}
    .rtime{{font-family:var(--mono);font-size:11px;color:var(--muted)}}
    .rimpact{{font-family:var(--mono);font-size:11px;color:var(--faint);border:1px solid rgba(255,255,255,.12);padding:3px 8px;border-radius:999px;background:rgba(255,255,255,.04)}}
    .rtitle{{margin-top:6px;display:block;font-size:16px;font-weight:850;line-height:1.25}}
    .rsumm{{margin-top:6px;color:var(--muted);font-size:14px;line-height:1.5}}

    /* GRID */
    .grid3{{display:grid;grid-template-columns: repeat(3, minmax(0, 1fr));gap:14px}}
    @media (max-width: 1160px){{.grid3{{grid-template-columns: repeat(2, minmax(0, 1fr));}}}}
    @media (max-width: 780px){{.grid3{{grid-template-columns: 1fr;}}}}

    /* ZONES (按品种) */
    .tlist{{padding:12px 14px 16px;display:flex;flex-direction:column;gap:10px}}
    .titem{{border:1px solid rgba(255,255,255,.10);background:rgba(0,0,0,.12);border-radius:16px;padding:10px 10px}}
    .tmeta{{display:flex;justify-content:space-between;gap:10px;align-items:baseline;flex-wrap:wrap}}
    .ttime{{font-family:var(--mono);font-size:12.5px;color:var(--muted)}}
    .tsrc{{font-family:var(--mono);font-size:12.5px;color:var(--faint)}}
    .ttitle{{margin-top:6px;display:block;font-size:16px;font-weight:820;line-height:1.25}}

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
          <span class=\"pill\">交易台模式（主线→雷达→分品种）</span>
          <span class=\"pill\">最后更新：{esc(generated)}（北京时间）</span>
          <span class=\"pill\">数据：briefs.json</span>
        </div>
        <h1>DayNews · {date}</h1>
        <p class=\"sub\">先读主线结论（3秒），再扫事件雷达（30秒），最后按品种浏览（3分钟）。</p>
      </header>

      {render_thesis()}
      {render_radar()}

      <div class=\"grid3\">
        {render_zone('指数（NQ/ES）','Index',zone_index)}
        {render_zone('黄金（GC）','Gold',zone_gold)}
        {render_zone('期权（QQQ/SPY/权重）','Options',zone_options)}
      </div>

      <section class=\"card\"><h2><span>其他（弱化）</span><span class=\"badge\">{len((sec_by.get('其他') or {}).get('items') or [])}</span></h2><div class=\"tlist\">{('<div class="note">（暂无）</div>' if not (sec_by.get('其他') or {}).get('items') else '')}</div></section>
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
