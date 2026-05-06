#!/usr/bin/env python3
"""
生成主线结论：数据驱动的市场分析
直接从 yfinance 获取实时行情 + RSS 头条 + 翻译
"""
import json
import sys
from pathlib import Path

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


def get_rss_headlines(limit=20):
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
                headlines.append({'headline': h, 'source': src, 'url': url})
            if len(headlines) >= limit:
                break
        return headlines
    except Exception:
        return []


def categorize_headlines(headlines):
    """将头条按主题分类"""
    fed, tech, geo, macro, earnings = [], [], [], [], []

    fed_kw = ['fed ', 'federal reserve', 'powell', 'interest rate', 'fomc',
               'treasury', 'bond yield', '10-year', '2-year', 'bessent']
    tech_kw = ['nvidia', 'apple', 'microsoft', 'google', 'alphabet', 'meta ',
                'amazon', 'tesla', 'amd', 'ai ', 'semiconductor', 'chip ',
                'openai', 'gpt', 'claude', 'broadcom', 'qualcomm', 'arm']
    geo_kw = ['iran', 'israel', 'china', 'russia', 'ukraine', 'tariff',
               'trade war', 'ceasefire', 'sanction', 'opec', 'saudi']
    earn_kw = ['earnings', 'revenue', 'profit', 'quarter', 'q1', 'q2',
                'fiscal', ' eps ', 'guidance', 'beat', 'miss']

    for h in headlines:
        txt = h['headline'].lower()
        if any(k in txt for k in fed_kw):
            fed.append(h['headline'])
        elif any(k in txt for k in tech_kw):
            tech.append(h['headline'])
        elif any(k in txt for k in geo_kw):
            geo.append(h['headline'])
        elif any(k in txt for k in earn_kw):
            earnings.append(h['headline'])
        else:
            macro.append(h['headline'])

    return {'fed': fed, 'tech': tech, 'geo': geo, 'macro': macro, 'earnings': earnings}


def generate_thesis(mdata, headlines, cats):
    """基于真实数据生成市场主线结论"""
    lines = []

    # ── 1. 市场走势 ───────────────────────────────────────
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

    if spy_chg > 0.5 and qqq_chg > 0.5:
        direction = f"美股强势上涨，标普{spy_chg:+.2f}% 纳指{qqq_chg:+.2f}%"
    elif spy_chg > 0:
        direction = f"美股小幅走强，标普{spy_chg:+.2f}% 纳指{qqq_chg:+.2f}%"
    elif spy_chg < -0.5:
        direction = f"美股承压下跌，标普{spy_chg:+.2f}% 纳指{qqq_chg:+.2f}%"
    else:
        direction = f"美股震荡整理，标普{spy_chg:+.2f}% 纳指{qqq_chg:+.2f}%"

    if vix_price > 25:
        vix_stmt = f"VIX {vix_price:.1f}({vix_chg:+.1f}%)偏高，市场紧张"
    elif vix_price > 18:
        vix_stmt = f"VIX {vix_price:.1f}({vix_chg:+.1f}%)中性"
    else:
        vix_stmt = f"VIX {vix_price:.1f}({vix_chg:+.1f}%)偏低，风险偏好升温"

    lines.append(f"**市场走势**：{direction}，{vix_stmt}")

    # ── 2. 核心驱动 ───────────────────────────────────────
    drivers = []

    if tnx_price > 0:
        if tnx_chg > 0:
            drivers.append(f"10Y美债收益率{tnx_price:.2f}%({tnx_chg:+.1f}%)回升，利率压力")
        else:
            drivers.append(f"10Y美债收益率{tnx_price:.2f}%({tnx_chg:+.1f}%)回落，宽松预期升温")

    # 翻译标题后再展示
    if cats['fed']:
        drivers.append(f"美联储/宏观：{translate_zh(cats['fed'][0])[:75]}")
    if cats['geo']:
        drivers.append(f"地缘/能源：{translate_zh(cats['geo'][0])[:75]}")
    if cats['tech']:
        drivers.append(f"科技/AI：{translate_zh(cats['tech'][0])[:75]}")
    if cats['earnings']:
        drivers.append(f"财报动态：{translate_zh(cats['earnings'][0])[:75]}")

    lines.append("")
    lines.append("**核心驱动**：")
    for d in drivers[:4]:
        lines.append(f"• {d}")

    # ── 3. 今日重大事件 ────────────────────────────────────
    lines.append("")
    lines.append("**今日重大事件**：")

    key_events = []
    for h in headlines:
        txt = h['headline']
        lower = txt.lower()
        if any(k in lower for k in ['surge', 'plunge', 'soar', 'jump', 'break',
                                      'record', 'deal', 'agreement', 'announcement',
                                      'ban ', 'block', 'investigation', 'selloff']):
            key_events.append(translate_zh(txt)[:90])

    for ev in key_events[:4]:
        lines.append(f"• {ev}")

    if not key_events:
        sample = [translate_zh(h['headline'])[:90] for h in headlines[:3]]
        lines.extend([f"• {s}" for s in sample])

    # ── 4. 风险提示 ────────────────────────────────────────
    lines.append("")
    lines.append("**风险提示**：")

    risks = []
    if vix_price > 20:
        risks.append("VIX 仍偏高，波动率风险未完全消除")
    if cats['geo']:
        risks.append("地缘事件仍存不确定性，可能快速逆转市场情绪")
    if cats['earnings']:
        risks.append("财报密集期，个股分化显著，注意仓位风险")
    if tnx_price > 4.5:
        risks.append("10Y 利率高于 4.5%，成长股估值压力持续")
    if not risks:
        risks.append("市场情绪稳定，注意美债收益率和地缘动向")

    for r in risks[:2]:
        lines.append(f"• {r}")

    return "\n".join(lines)


def main():
    print("📊 Generating market thesis (data-driven, Chinese)...", file=sys.stderr)

    mdata = get_market_data()
    headlines = get_rss_headlines()
    cats = categorize_headlines(headlines)

    analysis = generate_thesis(mdata, headlines, cats)
    print(analysis)
    return 0


if __name__ == "__main__":
    sys.exit(main())
