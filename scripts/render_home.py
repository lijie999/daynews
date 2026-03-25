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
        
        # S级：突发地缘/重大企业事件（数据发布已移到数据日历）
        # 排除常规盘前/盘后总结
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
                # 地缘突发
                "strikes",
                "struck",
                "missile attack",
                "ceasefire announced",
                "emergency meeting",
                # 重大企业事件
                "bankruptcy",
                "chapter 11",
                "delisting",
                "acquisition announced",
                "merger approved",
                # Fed 特别事件（非常规会议/紧急声明）
                "fomc emergency",
                "fed emergency statement",
            ]
        )
        
        # A级：重要财报、政策转向信号、持续主题监控
        warm = any(
            k in t
            for k in [
                # 财报季
                "earnings",
                "guidance",
                "revenue miss",
                "profit warning",
                # 监管/诉讼
                "sec charges",
                "doj",
                "lawsuit filed",
                "antitrust",
                # 政策/地缘持续主题
                "tariff",
                "fed speaker",
                "powell",
                "iran",
                "israel",
                "oil",
                "opec",
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

        # 调用专用的主线结论生成器（使用 web_search）
        analysis = None
        try:
            result = subprocess.run(
                ["python3", str(REPO_DIR / "scripts" / "generate_thesis.py")],
                capture_output=True,
                text=True,
                timeout=70,
                cwd=str(REPO_DIR)
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                # 移除可能的 markdown 代码块标记
                output = output.replace("```markdown", "").replace("```", "").strip()
                # 验证格式
                if output and "**市场走势**" in output and len(output) > 50:
                    analysis = output
                else:
                    print(f"warn: thesis generator returned invalid format", file=sys.stderr)
        except Exception as e:
            print(f"warn: thesis generator failed: {e}", file=sys.stderr)
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

    def render_data_calendar() -> str:
        """
        数据日历：今日/明日重点经济数据发布提醒（⭐⭐⭐ 三星级）
        """
        import datetime as dt
        
        today = now.date()
        tomorrow = today + dt.timedelta(days=1)
        
        # 硬编码关键数据日历（每月固定日期）
        # 格式：(月日范围, 星期几, 时间, 名称, 重要性)
        calendar_rules = [
            # CPI：每月10-14日，通常13日 08:30
            ((10, 14), None, "08:30", "美国CPI月率/年率", "⭐⭐⭐"),
            # NFP：每月第一个周五 08:30
            (None, 4, "08:30", "非农就业人数（NFP）", "⭐⭐⭐"),
            # FOMC：每6-8周（3/5/6/7/9/11/12月中旬）
            ((14, 21), 2, "02:00", "美联储FOMC利率决议", "⭐⭐⭐"),
            # PMI：每月第一个工作日
            ((1, 3), None, "09:45", "美国Markit PMI初值", "⭐⭐"),
            # 零售销售：每月15-17日 08:30
            ((15, 17), None, "08:30", "美国零售销售月率", "⭐⭐"),
            # 初请失业金：每周四 08:30
            (None, 3, "08:30", "初请失业金人数", "⭐⭐"),
            # GDP：季度末月下旬
            ((25, 30), None, "08:30", "美国GDP季率初值", "⭐⭐⭐"),
        ]
        
        def check_date(rule, check_day):
            day_range, weekday, time_str, name, stars = rule
            
            # 检查日期范围
            if day_range:
                if not (day_range[0] <= check_day.day <= day_range[1]):
                    return None
            
            # 检查星期几（0=周一, 4=周五）
            if weekday is not None:
                if check_day.weekday() != weekday:
                    return None
            
            return (time_str, name, stars)
        
        today_events = []
        tomorrow_events = []
        
        for rule in calendar_rules:
            result = check_date(rule, today)
            if result:
                today_events.append(result)
            
            result = check_date(rule, tomorrow)
            if result:
                tomorrow_events.append(result)
        
        # 生成HTML（先处理数据日历部分）
        html_parts = ['<div class="panel">',
                      '<h3><span>📅 数据日历</span><span class="badge">重点发布</span></h3>',
                      '<div class="calendar-body">']
        
        if today_events:
            html_parts.append('<div class="calendar-day"><strong>今日：</strong></div>')
            for time_str, name, stars in today_events:
                html_parts.append(
                    f'<div class="calendar-item">'
                    f'<span class="cal-time">{time_str}</span> {esc(name)} <span class="cal-stars">{stars}</span>'
                    f'</div>'
                )
        
        if tomorrow_events:
            html_parts.append('<div class="calendar-day"><strong>明日：</strong></div>')
            for time_str, name, stars in tomorrow_events:
                html_parts.append(
                    f'<div class="calendar-item">'
                    f'<span class="cal-time">{time_str}</span> {esc(name)} <span class="cal-stars">{stars}</span>'
                    f'</div>'
                )
        
        # 如果今明都没有数据，显示占位
        if not today_events and not tomorrow_events:
            html_parts.append('<div class="note">（今明两日无⭐⭐⭐级数据发布）</div>')
        
        # 本周财报提醒
        # 策略1：从现有新闻中提取
        earnings_from_news = []
        important_tickers = {
            "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA",
            "JPM", "BAC", "WFC", "GS", "MS", "UNH", "JNJ", "PG", "XOM", "CVX",
            "NFLX", "AMD", "INTC", "ORCL", "CRM", "SHOP", "SQ", "COIN",
            "BABA", "JD", "PDD", "BIDU", "NIO", "XPEV"
        }
        
        for sec in sections:
            items = sec.get("items", [])
            for it in items[:20]:
                title = (it.get("title") or "").lower()
                ticker = (it.get("ticker") or "").upper()
                
                if ("earnings" in title or "报告" in title or "财报" in title) and ticker in important_tickers:
                    company_map = {
                        "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia",
                        "TSLA": "Tesla", "AMZN": "Amazon", "META": "Meta",
                        "GOOGL": "Google", "GOOG": "Google"
                    }
                    company_name = company_map.get(ticker, ticker)
                    
                    time_hint = "盘前" if any(k in title for k in ["before market", "盘前"]) else \
                                "盘后" if any(k in title for k in ["after hours", "after market", "盘后"]) else \
                                "本周"
                    
                    earnings_from_news.append({
                        "company": f"{company_name} ({ticker})",
                        "time": time_hint,
                        "ticker": ticker
                    })
        
        # 策略2：硬编码财报季（Q1: 4月中下旬, Q2: 7月中下旬, Q3: 10月中下旬, Q4: 1月下旬-2月初）
        # 当前是否在财报季窗口
        month = today.month
        day = today.day
        
        earnings_season_companies = []
        
        # Q4 财报季（1月20日-2月15日）
        if (month == 1 and day >= 20) or (month == 2 and day <= 15):
            earnings_season_companies = [
                ("本周", "Apple (AAPL)"),
                ("本周", "Microsoft (MSFT)"),
                ("本周", "Alphabet (GOOGL)"),
                ("本周", "Amazon (AMZN)"),
                ("本周", "Meta (META)"),
            ]
        
        # Q1 财报季（4月15日-5月5日）
        elif (month == 4 and day >= 15) or (month == 5 and day <= 5):
            earnings_season_companies = [
                ("本周", "Tesla (TSLA)"),
                ("本周", "Netflix (NFLX)"),
                ("本周", "Microsoft (MSFT)"),
            ]
        
        # Q2 财报季（7月15日-8月5日）
        elif (month == 7 and day >= 15) or (month == 8 and day <= 5):
            earnings_season_companies = [
                ("本周", "Apple (AAPL)"),
                ("本周", "Amazon (AMZN)"),
                ("本周", "Meta (META)"),
            ]
        
        # Q3 财报季（10月15日-11月5日）
        elif (month == 10 and day >= 15) or (month == 11 and day <= 5):
            earnings_season_companies = [
                ("本周", "Alphabet (GOOGL)"),
                ("本周", "Microsoft (MSFT)"),
                ("本周", "Amazon (AMZN)"),
            ]
        
        # 合并新闻提取 + 硬编码季节
        all_earnings = earnings_from_news[:] if earnings_from_news else earnings_season_companies
        
        # 去重
        seen_tickers = set()
        unique_earnings = []
        for item in all_earnings:
            # 从 "Company (TICKER)" 格式提取 ticker
            ticker = item.get("ticker") or (item[1].split("(")[-1].rstrip(")") if isinstance(item, tuple) else "")
            if ticker and ticker not in seen_tickers:
                seen_tickers.add(ticker)
                if isinstance(item, tuple):
                    unique_earnings.append({"time": item[0], "company": item[1]})
                else:
                    unique_earnings.append(item)
        
        # 如果有财报，追加到HTML
        if unique_earnings:
            html_parts.append('<div class="calendar-day" style="margin-top:16px"><strong>📊 本周财报：</strong></div>')
            for item in unique_earnings[:6]:
                time_str = item["time"]
                html_parts.append(
                    f'<div class="calendar-item earnings-item">'
                    f'<span class="cal-time">{time_str}</span> {esc(item["company"])}'
                    f'</div>'
                )
        else:
            # 非财报季时显示占位提示
            next_season = ""
            if month <= 3:
                next_season = "4月中旬起Q1财报季"
            elif month <= 6:
                next_season = "7月中旬起Q2财报季"
            elif month <= 9:
                next_season = "10月中旬起Q3财报季"
            else:
                next_season = "次年1月下旬起Q4财报季"
            
            html_parts.append(
                '<div class="calendar-day" style="margin-top:16px"><strong>📊 本周财报：</strong></div>'
                f'<div class="note" style="padding:10px 12px">（本周无重点财报，{next_season}）</div>'
            )
        
        html_parts.append('</div></div>')
        
        return '\n'.join(html_parts)

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

    def render_zone(name: str, items: list[dict]) -> str:
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
        # badge 显示条数，name 包含emoji和描述
        return (
            '<section class="card">'
            f'<h2><span>{esc(name)}</span><span class="badge">{len(uniq)}</span></h2>'
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

    # 新板块划分（方案A）
    zone_index_tech = pick_items("七姐妹与半导体链")  # 指数/科技：FAANG + 半导体
    zone_energy_geo = pick_items("地缘/能源/避险")    # 能源/地缘：黄金 + 油价 + 地缘冲突
    zone_fed_policy = pick_items("美联储与政策")      # 美联储/政策：利率 + CPI + 财政

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

    /* DATA CALENDAR */
    .data-calendar .calendar-body{{padding:14px 16px 18px;display:flex;flex-direction:column;gap:8px}}
    .calendar-day{{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:8px;margin-bottom:4px}}
    .calendar-item{{font-size:14.5px;line-height:1.6;color:var(--text);padding:10px 12px;background:rgba(0,0,0,.12);border-radius:12px;border:1px solid rgba(255,255,255,.10)}}
    .cal-time{{font-family:var(--mono);font-size:12px;color:var(--faint);border:1px solid rgba(255,255,255,.12);padding:3px 8px;border-radius:999px;background:rgba(255,255,255,.04);margin-right:8px}}
    .cal-stars{{font-size:13px;color:#fbbf24;margin-left:6px}}

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
    .grid3{{display:grid;grid-template-columns: repeat(3, minmax(0, 1fr));gap:16px}}
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
          <span class=\"pill\">交易台模式（主线→AI→主题）</span>
          <span class=\"pill\">最后更新：{esc(generated)}（北京时间）</span>
          <span class=\"pill\">数据：briefs.json</span>
        </div>
        <h1>DayNews · {date}</h1>
        <p class=\"sub\">先读主线结论（3秒），再看AI动态（10秒），最后按主题浏览（3分钟）。</p>
      </header>

      {render_thesis()}

      <div class=\"grid3\">
        {render_zone('📊 指数/科技',zone_index_tech)}
        {render_zone('⚡ 能源/地缘',zone_energy_geo)}
        {render_zone('💵 美联储/政策',zone_fed_policy)}
      </div>

      <section class=\"card\"><h2><span>其他</span><span class=\"badge\">{len((sec_by.get('其他') or {}).get('items') or [])}</span></h2><div class=\"tlist\">{('<div class="note">（暂无）</div>' if not (sec_by.get('其他') or {}).get('items') else '')}</div></section>
    </main>

    <aside class=\"side\">
      {render_data_calendar()}
    </aside>
  </div>
</body>
</html>
"""

    OUT.write_text(page, encoding="utf-8")
    
    # 生成完主页后，立即注入 AI 新闻
    print("📰 Injecting AI news...")
    import subprocess
    inject_script = REPO_DIR / "scripts" / "inject_ai_news.py"
    if inject_script.exists():
        result = subprocess.run(
            ["python3", str(inject_script)],
            cwd=REPO_DIR,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✅ AI news injected successfully")
        else:
            print(f"⚠️  AI news injection failed: {result.stderr}")
    else:
        print(f"⚠️  inject_ai_news.py not found at {inject_script}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
