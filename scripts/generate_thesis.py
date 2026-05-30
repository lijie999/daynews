#!/usr/bin/env python3
"""
生成主线结论：数据驱动的市场分析
直接从 yfinance 获取实时行情 + RSS 头条 + 翻译

新结构（三行速读）：
  🟢 看多信号（≤3条）
  🔴 看空信号（≤3条）
  ⚡ 今日最大变量（1句话）
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter

REPO_DIR = Path(__file__).resolve().parent.parent

# 翻译支持
try:
    sys.path.insert(0, str(REPO_DIR / "scripts"))
    from translate_mt import translate_zh, translate_batch
except Exception:
    translate_zh = lambda t: t
    translate_batch = lambda l: l


def get_market_data():
    """获取关键市场数据"""
    import yfinance as yf

    result = {}
    tickers_map = {
        'SPY': '^SPX',
        'QQQ': '^NDX',
        'VIX': '^VIX',
        'TNX': '^TNX',
        'UUP': 'UUP',
        'GCF': 'GC=F',
        'CLF': 'CL=F'
    }

    for label, sym in tickers_map.items():
        try:
            t = yf.Ticker(sym)
            h = t.history(period='2d')
            if h.empty or len(h) < 2:
                continue
            cur = float(h['Close'].iloc[-1])
            prev = float(h['Close'].iloc[-2])
            chg = (cur - prev) / prev * 100
            result[label] = {'price': cur, 'chg': chg}
        except Exception:
            pass

    return result


def get_rss_headlines(limit=40):
    """获取 RSS 头条"""
    cache = REPO_DIR / ".cache" / "rss_items.json"
    if not cache.exists():
        return []

    try:
        data = json.loads(cache.read_text(encoding='utf-8'))
        items = data.get('items', [])
        headlines = []
        for it in items:
            h = it.get('headline', it.get('title', '')).strip()
            src = it.get('source', '?')
            url = it.get('url', '')
            if h:
                headlines.append({
                    'headline': h,
                    'source': src,
                    'url': url,
                    'summary': it.get('summary', '')
                })
            if len(headlines) >= limit:
                break
        return headlines
    except Exception:
        return []


def _looks_english(s: str) -> bool:
    s = (s or "").strip()
    if not s:
        return False
    letters = sum(1 for ch in s if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    return letters >= 12


def _tx(s: str) -> str:
    """翻译（如果需要）"""
    if not s or not _looks_english(s):
        return s
    try:
        return translate_zh(s)
    except Exception:
        return s


def _is_cramer(h: str) -> bool:
    """过滤 Cramer 内容（节目评论，不是市场驱动）"""
    l = h.lower()
    return any(k in l for k in [
        'jim cramer', 'cramer says', 'cramer on', 'cramer:',
        'mad max', 'i think my nose', 'i was wrong',
        'the kramma', 'cramer"'
    ])


def _is_routine(s: str) -> bool:
    """过滤常规性内容（周报、回顾、推荐列表等非事件驱动）"""
    l = s.lower()
    return any(k in l for k in [
        'week ahead', 'stock market week', 'what to watch',
        'best stocks to', 'analyst favorites', 'rating: buy',
        'retirement mistake', 'social security', 'credit card',
        'dave ramsey', 'billionaire', 'portfolio', 'Alpha Check',
    ]) or s.startswith('Is ') or s.startswith('Is ')


def _is_question(s: str) -> bool:
    """过滤问句格式（推荐类、列表类文章标题）"""
    return '?' in s or s.startswith('Is ') or s.startswith('Should ') or s.startswith('Can ')


# ── 信号识别规则 ────────────────────────────────────────────

BULL_PATTERNS = [
    (r'\b(surge|soar|jump|pop|rally)\b', "技术性上涨"),
    (r'\b(gain [123]\d%|up [123]\d%)\b', "大幅走强"),
    (r'\b(new high|record high|all.time high|ATH)\b', "价格创新高"),
    (r'\b(beat|beats|exceed|blows out|in line)\b', "财报超预期"),
    (r'\b(fed dovish|ease|easing|cut rates|cutting rates|rate cut|pivot)\b', "美联储宽松"),
    (r'\b(ceasefire|peace deal|deal done|agreement signed|truce)\b', "地缘缓和"),
    (r'\b(raises guidance|raises forecast|boosts outlook|upside)\b', "上调指引"),
    (r'\b(acquisition|merger|buyout|deal)\b', "并购消息"),
    (r'\b(ai deal|defense contract|government contract|pentagon|deal done)\b', "AI/国防订单"),
    (r'\b(highs|hit highs|leads? [123])\b', "领涨"),
    (r'\b(buy now|best to buy|strong buy|overweight)\b', "机构看多"),
]

BEAR_PATTERNS = [
    (r'\b(plunge|drop [123]\d%|fall [123]\d%|tumble|retreat|slide)\b', "技术性下跌"),
    (r'\b(new low|record low|all.time low|ATL)\b', "价格创新低"),
    (r'\b(miss|misses|below estimate|warns|guidance cut|cuts outlook)\b', "财报低于预期"),
    (r'\b(fed hawkish|tighten|rate hike|hiking rates)\b', "美联储紧缩"),
    (r'\b(strike|attack|missile|blasts?|sanctions|retaliat|conflict)\b', "地缘冲突升级"),
    (r'\b(vix spike|vix up|vix >|fear|panic|ticking time bomb)\b', "VIX飙升/恐慌"),
    (r'\b(lawsuit|sec|doj|investigation|antitrust|ban|block|delisting)\b', "监管风险"),
    (r'\b(inflation hotter|price pressure|wage pressure|cpi jump)\b', "通胀担忧"),
    (r'\b(selloff|sell.off|breakdown|support fail)\b', "破位下行"),
    (r'\b(warning|stark warning)\b', "警告信号"),
]

DRIVER_PATTERNS = [
    (r'\b(tariff|trade war|trade deal)\b', "关税/贸易战"),
    (r'\b(fed meeting|fomc|rate decision|powell)\b', "美联储政策"),
    (r'\b(iran|israel|gaza|ukraine|russia|china|nato)\b', "地缘风险"),
    (r'\b(oil|opec|saudi|energy|brent|wti crude)\b', "能源价格"),
    (r'\b(nvidia|ai chip|gpu|semiconductor|arm|avgo|amd|qualcomm)\b', "AI/半导体"),
    (r'\b(treasury|yield|10.year|2.year|bond auction)\b', "美债收益率"),
    (r'\b(earnings|quarterly results|q[1234])\b', "财报季"),
    (r'\b(robotaxi|tesla|optimus|fsd|autonomous)\b', "特斯拉/自动驾驶"),
    (r'\b(inflation|cpi|pce|ppi|gdp|payroll|jobs)\b', "宏观数据"),
    (r'\b(earnings growth|growth story|ai boom)\b', "AI/增长主题"),
]


def _match(s: str, patterns: list) -> tuple[bool, str]:
    for pat, label in patterns:
        if re.search(pat, s, re.I):
            return True, label
    return False, ""


def _signal_label(item: dict) -> tuple[str, str]:
    """给一条新闻打标签：(信号类型, 标签)"""
    t = ((item.get('headline') or '') + ' ' + (item.get('summary', '')))
    bull, blabel = _match(t, BULL_PATTERNS)
    bear, belabel = _match(t, BEAR_PATTERNS)
    if bull and not bear:
        return "bull", blabel
    if bear and not bull:
        return "bear", belabel
    if bull and bear:
        return "mixed", f"{blabel}+{belabel}"
    return "neutral", ""


def _driver_label(item: dict) -> str:
    """识别今日最大变量"""
    t = ((item.get('headline') or '') + ' ' + (item.get('summary', '')))
    for pat, label in DRIVER_PATTERNS:
        if re.search(pat, t, re.I):
            return label
    return ""


def generate_thesis(mdata: dict, headlines: list[dict]) -> str:
    """
    三行速读结构主线结论
    """
    lines: list[str] = []

    # ── 市场技术面 ─────────────────────────────────────────
    spy = mdata.get('SPY', {})
    qqq = mdata.get('QQQ', {})
    vix = mdata.get('VIX', {})
    tnx = mdata.get('TNX', {})

    spy_chg = spy.get('chg', 0)
    qqq_chg = qqq.get('chg', 0)
    vix_price = vix.get('price', 0)
    vix_chg = vix.get('chg', 0)
    tnx_price = tnx.get('price', 0)
    tnx_chg = tnx.get('chg', 0)

    # 描述市场走势（必须有 **市场走势** 供 render_thesis() 验证）
    if spy_chg > 0.5 and qqq_chg > 0.5:
        direction = f"美股强势上涨，标普{spy_chg:+.2f}% 纳指{qqq_chg:+.2f}%"
    elif spy_chg > 0:
        direction = f"美股小幅走强，标普{spy_chg:+.2f}% 纳指{qqq_chg:+.2f}%"
    elif spy_chg < -0.5:
        direction = f"美股承压下跌，标普{spy_chg:+.2f}% 纳指{qqq_chg:+.2f}%"
    else:
        direction = f"美股震荡整理，标普{spy_chg:+.2f}% 纳指{qqq_chg:+.2f}%"

    if vix_price > 20:
        vix_stmt = f"VIX {vix_price:.1f} 偏高，波动风险升温"
    elif vix_price < 15:
        vix_stmt = f"VIX {vix_price:.1f} 偏低，风险偏好强"
    else:
        vix_stmt = f"VIX {vix_price:.1f} 中性"

    lines.append(f"**市场走势**：{direction}，{vix_stmt}")

    # ── 收集信号 ───────────────────────────────────────────
    tech_bull, tech_bear = [], []
    news_bull, news_bear = [], []
    driver_candidates = []

    # 技术面信号（直接来自价格变化）
    if spy_chg > 0.5:
        tech_bull.append(f"标普+{spy_chg:+.2f}%（技术偏多）")
    elif spy_chg < -0.5:
        tech_bear.append(f"标普{spy_chg:+.2f}%（技术偏空）")
    if qqq_chg > 0.5:
        tech_bull.append(f"纳指+{qqq_chg:+.2f}%（科技偏多）")
    elif qqq_chg < -0.5:
        tech_bear.append(f"纳指{qqq_chg:+.2f}%（科技偏空）")
    if vix_price > 20:
        tech_bear.append(f"VIX {vix_price:.1f} 偏高（波动风险）")
    elif vix_price < 15:
        tech_bull.append(f"VIX {vix_price:.1f} 偏低（风险偏好强）")
    if tnx_chg < -0.05:
        tech_bull.append(f"10Y {tnx_price:.2f}% 回落（宽松预期升温）")
    elif tnx_chg > 0.05:
        tech_bear.append(f"10Y {tnx_price:.2f}% 攀升（利率压力）")

    # 新闻信号（排除 Cramer 和常规内容）
    for h in headlines:
        headline = h.get('headline', '')
        if _is_cramer(headline):
            continue
        if _is_routine(headline):
            continue
        if _is_question(headline):
            continue
        sig, label = _signal_label(h)
        drv = _driver_label(h)
        if drv:
            driver_candidates.append(drv)
        if sig == "bull":
            news_bull.append(headline)
        elif sig == "bear":
            news_bear.append(headline)

    all_bull = tech_bull[:]
    all_bear = tech_bear[:]

    for hl in news_bull[:4]:
        short = _tx(hl)[:72].strip()
        if short:
            all_bull.append(short)
    for hl in news_bear[:4]:
        short = _tx(hl)[:72].strip()
        if short:
            all_bear.append(short)

    # ── 今日最大变量 ────────────────────────────────────────
    drv_counts = Counter(driver_candidates)
    if drv_counts:
        top_driver = drv_counts.most_common(1)[0][0]
    else:
        if tnx_price > 4.6:
            top_driver = "美债收益率突破4.6%（利率压力）"
        elif vix_price > 20:
            top_driver = "VIX 飙升（波动率风险）"
        elif tech_bull:
            top_driver = "技术面支撑偏多（指数走强）"
        elif tech_bear:
            top_driver = "技术面压力偏空（指数承压）"
        else:
            top_driver = "宏观政策/地缘主导"

    # ── 输出（3行结构）────────────────────────────────────
    lines.append("")
    lines.append("🟢 看多信号：")
    if all_bull:
        for sig in all_bull[:3]:
            lines.append(f"• {sig}")
    else:
        lines.append("• 无明确信号（VIX 低位，市场偏稳）")

    lines.append("")
    lines.append("🔴 看空信号：")
    if all_bear:
        for sig in all_bear[:3]:
            lines.append(f"• {sig}")
    else:
        lines.append("• 无明确信号（市场未出现明显恐慌）")

    lines.append("")
    lines.append(f"⚡ 今日最大变量：{top_driver}")

    return "\n".join(lines)


def main():
    print("📊 Generating market thesis (3-row format)...", file=sys.stderr)

    mdata = get_market_data()
    headlines = get_rss_headlines()

    analysis = generate_thesis(mdata, headlines)
    print(analysis)
    return 0


if __name__ == "__main__":
    sys.exit(main())