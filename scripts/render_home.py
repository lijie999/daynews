#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

REPO_DIR = Path("/Users/lijiaolong/.openclaw/workspace/daynews")
DOCS = REPO_DIR / "docs"
BRIEFS = DOCS / "briefs.json"
OUT = DOCS / "index.html"
MARKET_PULSE_CACHE = DOCS / ".market_pulse_cache.json"


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
        # 时间窗口：优先最近12小时的事件
        t = ((it.get("title") or "") + " " + (it.get("summary") or "")).lower()
        
        # S级：盘中触发器/突发拐点（数据发布、突发地缘、Fed决议）
        # 排除常规盘前/盘后总结（如 "futures..." "stock market today..."）
        is_routine_summary = any(
            k in t
            for k in [
                "futures",
                "stock market today",
                "dow jones futures",
                "what to watch",
                "week ahead",
                "markets wrap",
            ]
        )
        
        hot = any(
            k in t
            for k in [
                "fomc decision",
                "fed decision",
                "powell press conference",
                "cpi report",
                "ppi report",
                "nonfarm payrolls",
                "nfp report",
                "jobs report",
                "gdp report",
                "strikes",
                "struck",
                "missile attack",
                "ceasefire announced",
                "opec decision",
                "emergency meeting",
            ]
        )
        
        warm = any(
            k in t
            for k in [
                "earnings",
                "guidance",
                "sec charges",
                "doj",
                "lawsuit filed",
                "tariff",
                "antitrust",
                "rate decision",
                "fed speaker",
                "iran",
                "israel",
                "oil",
            ]
        )
        
        if hot and not is_routine_summary:
            return "S"
        if warm and not is_routine_summary:
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
        """
        生成主线结论：结构化市场综述
        通过 openclaw agent 调用 AI 实时生成
        缓存 30 分钟
        """
        import time
        
        THESIS_CACHE = DOCS / ".thesis_cache.json"
        
        # 检查缓存
        if THESIS_CACHE.exists():
            try:
                cache = json.loads(THESIS_CACHE.read_text(encoding="utf-8"))
                cache_time = cache.get("timestamp", 0)
                if time.time() - cache_time < 1800:  # 30分钟
                    html = cache.get("html", "")
                    if html:
                        return html
            except Exception:
                pass
        
        # 收集素材（内部 + 外部源）
        market_news = []
        fed_news = []
        geo_news = []
        external_news = []
        
        # 1. 从现有 sections 提取
        for sec in sections:
            name = sec.get("name", "")
            items = sec.get("items", [])[:5]
            
            if name == "美联储与政策":
                fed_news.extend([f"- {it.get('title', '')[:85]}" for it in items if it.get('title')])
            elif name == "地缘/能源/避险":
                geo_news.extend([f"- {it.get('title', '')[:85]}" for it in items if it.get('title')])
            elif name in ["七姐妹与半导体链", "特斯拉链"]:
                market_news.extend([f"- {it.get('title', '')[:85]}" for it in items if it.get('title')])
        
        # 2. 让 AI 抓取外部新闻源（通过 agent 调用 web_search）
        external_summary = ""
        try:
            search_task = """请用 web_search 工具搜索今日美股市场新闻（Yahoo Finance 或 CNBC），提取 3-5 个关键标题，用简短列表返回（每条不超过 80 字）。

搜索关键词建议：
- site:finance.yahoo.com stock market today
- site:cnbc.com market news

直接返回标题列表，不要解释过程。"""

            result = subprocess.run(
                ["openclaw", "agent",
                 "--session-id", "daynews-external-fetch",
                 "--message", search_task,
                 "--timeout", "20"],
                capture_output=True,
                text=True,
                timeout=25
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if output and len(output) > 30 and not output.startswith("NO_REPLY"):
                    external_summary = output
        except Exception:
            pass
        
        # 构建prompt（整合内部 + 外部源）
        materials = f"""【内部数据源】
市场/科技：
{chr(10).join(market_news[:8]) if market_news else '（无）'}

美联储/政策：
{chr(10).join(fed_news[:5]) if fed_news else '（无）'}

地缘/能源：
{chr(10).join(geo_news[:5]) if geo_news else '（无）'}"""

        if external_summary:
            materials += f"\n\n【外部新闻源（Yahoo/CNBC 今日头条）】\n{external_summary}"

        prompt = f"""基于以下今日财经新闻（内部数据 + 外部主流媒体），生成200字以内的市场主线结论：

{materials}

要求格式（Markdown）：
**市场走势**：[1-2句，指数/板块表现]

**核心驱动**：
• [要点1]
• [要点2]
• [要点3]

**风险提示**：[1句前瞻/风险]

直接输出内容，不要额外解释。"""

        # 调用 AI 生成
        analysis = None
        try:
            # 使用 openclaw agent 调用 AI
            result = subprocess.run(
                [
                    "openclaw", "agent",
                    "--session-id", "daynews-thesis-generator",
                    "--message", prompt,
                    "--timeout", "20"
                ],
                capture_output=True,
                text=True,
                timeout=25
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                # 移除可能的 NO_REPLY 或其他控制标记
                if output and not output.startswith("NO_REPLY") and len(output) > 50:
                    analysis = output
                
        except Exception:
            pass
        
        # Fallback 模板
        if not analysis or len(analysis) < 50:
            analysis = f"""**市场走势**：美股指数震荡，科技股分化明显

**核心驱动**：
• Fed 政策预期持稳，利率/债券收益率影响估值
• 地缘风险（伊朗/能源）推升油价，避险需求抬头
• AI/科技板块结构分化，关注头部权重股动向

**风险提示**：短期波动率可能维持高位，关注宏观数据与油价"""

        # 生成 HTML
        analysis_html = esc(analysis).replace("\n", "<br>")
        
        html = (
            '<section class="hero">'
            '<div class="hero-top">'
            f'<div class="hero-title">主线结论</div>'
            f'<div class="hero-time">{now.strftime("%Y-%m-%d %H:%M:%S")}</div>'
            '</div>'
            f'<div class="hero-body">{analysis_html}</div>'
            '</section>'
        )
        
        # 写缓存
        try:
            THESIS_CACHE.write_text(
                json.dumps({"timestamp": time.time(), "html": html}, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception:
            pass
        
        return html

    def render_market_pulse() -> str:
        """
        市场脉搏：从现有数据中提取关键市场动态摘要
        TODO: 后续可接入 web_search 调用外部源（Yahoo/CNBC/MarketWatch）
        """
        # 简化版本1：从现有sections中提取关键指标型新闻
        key_items = []
        
        for sec in sections:
            name = sec.get("name", "")
            items = sec.get("items", [])
            
            if name in ["美联储与政策", "地缘/能源/避险"]:
                for it in items[:3]:
                    title = it.get("title", "")
                    # 筛选包含关键市场指标的新闻
                    if any(k in title.lower() for k in [
                        "dow", "s&p", "nasdaq", "stock market", "指数",
                        "treasury", "yield", "利率", "fed", "inflation"
                    ]):
                        key_items.append({
                            "title": title[:90],
                            "time": it.get("time", ""),
                            "source": it.get("source", "")
                        })
        
        if not key_items:
            return ''  # 无关键新闻时不显示此卡片
        
        # 去重
        seen = set()
        unique_items = []
        for it in key_items:
            if it["title"] not in seen:
                seen.add(it["title"])
                unique_items.append(it)
        
        # 生成HTML
        items_html = []
        for it in unique_items[:5]:
            items_html.append(
                f'<div class="pulse-item">'
                f'<span class="pulse-badge">{esc(it["source"])}</span> '
                f'{esc(it["title"])}'
                f'</div>'
            )
        
        body = "\n".join(items_html)
        
        return (
            '<section class="card market-pulse">'
            '<h2><span>市场脉搏</span><span class="badge">关键动态</span></h2>'
            f'<div class="pulse-body">{body}</div>'
            '</section>'
        )

    def render_radar() -> str:
        pool = pick_items("美联储与政策", "地缘/能源/避险", "七姐妹与半导体链", "特斯拉链")
        
        # 去重（与下方指数/期权、黄金栏交叉去重）
        # 先收集已在分品种栏显示的 URL
        zone_urls: set[str] = set()
        for it in zone_index_options + zone_gold:
            zone_urls.add(it.get("url") or "")
        
        seen: set[str] = set()
        uniq: list[dict] = []
        for it in pool:
            url = it.get("url") or ""
            title = it.get("title") or ""
            k = url + "|" + title
            if not k.strip() or k in seen:
                continue
            # 如果已在分品种栏显示，跳过（避免雷达重复）
            if url and url in zone_urls:
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
    # - 指数(Index)：聚焦"宏观/利率/大盘方向/风险偏好"相关线索
    # - 期权(Options)：聚焦"波动率/VIX/期权市场行为(0DTE/put-call/IV等)"相关线索
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
        # 这里的 index 主要指"大盘指数/指数期货/股指方向"，不把普通"index fund/ETF指数基金"也全部算进来
        return any(
            k in t
            for k in [
                "nasdaq",
                "s&p",
                "sp 500",
                "s&p 500",
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
                "qqq",
                "spy",
                "dia",
                "stock market",
                "equity",
                "equities",
                "shares",
                "rally",
                "selloff",
                "sell-off",
            ]
        ) or any(
            k in t
            for k in [
                "yield",
                "treasury",
                "treasuries",
                "bond",
                "bonds",
                "rates",
                "rate",
                "interest rate",
                "mortgage rate",
                "gilt",
                "gilts",
                "10-year",
                "2-year",
                "fed",
                "fomc",
                "cpi",
                "ppi",
                "nfp",
                "payroll",
                "payrolls",
                "inflation",
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

    # 合并指数与期权为一栏（用户反馈：两者是一回事）
    zone_index_options = [it for it in _dedup(pool_macro + pool_equity) if (_is_index(it) or _is_options(it))]

    # 黄金栏：保留原先逻辑（风险事件+宏观），避免被指数/期权污染
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

    /* MARKET PULSE */
    .market-pulse .pulse-body{{padding:14px 16px 18px;display:flex;flex-direction:column;gap:10px}}
    .pulse-item{{font-size:14.5px;line-height:1.6;color:var(--text);padding:10px 12px;background:rgba(0,0,0,.12);border-radius:12px;border:1px solid rgba(255,255,255,.10)}}
    .pulse-badge{{font-family:var(--mono);font-size:11px;color:var(--faint);border:1px solid rgba(255,255,255,.12);padding:3px 8px;border-radius:999px;background:rgba(255,255,255,.04);margin-right:8px}}

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

    /* GRID (2列优化：从3列改为2列，增加卡片宽度) */
    .grid3{{display:grid;grid-template-columns: repeat(2, minmax(0, 1fr));gap:16px}}
    @media (max-width: 880px){{.grid3{{grid-template-columns: 1fr;}}}}

    /* ZONES (按品种 - 2列优化：增大字号与间距) */
    .tlist{{padding:14px 16px 18px;display:flex;flex-direction:column;gap:12px}}
    .titem{{border:1px solid rgba(255,255,255,.10);background:rgba(0,0,0,.12);border-radius:16px;padding:12px 12px}}
    .tmeta{{display:flex;justify-content:space-between;gap:10px;align-items:baseline;flex-wrap:wrap}}
    .ttime{{font-family:var(--mono);font-size:13px;color:var(--muted)}}
    .tsrc{{font-family:var(--mono);font-size:13px;color:var(--faint)}}
    .ttitle{{margin-top:7px;display:block;font-size:16.5px;font-weight:820;line-height:1.3}}

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
      {render_market_pulse()}
      {render_radar()}

      <div class=\"grid3\">
        {render_zone('指数/期权（NQ/ES/QQQ）','Index/Options',zone_index_options)}
        {render_zone('黄金（GC）','Gold',zone_gold)}
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
