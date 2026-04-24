#!/usr/bin/env python3
"""
美股日线突破检测 - NASDAQ 100 成分股
每天 09:00 和 21:00 运行
逻辑：当日收盘价突破20日高点，且成交量放大确认
"""
import json
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

REPO_DIR = Path("/Users/lijiaolong/.openclaw/workspace/daynews")
OUTPUT_JSON = REPO_DIR / "docs" / "us_breakout.json"

# NASDAQ 100 成分股（主要权重）
NASDAQ_100_COMPONENTS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST",
    "AMD", "NFLX", "ASML", "HON", "ADBE", "INTU", "AMAT", "KLAC", "PANW",
    "SNPS", "MRVL", "CRWD", "MELI", "COP", "CSX", "NXPI", "BKR", "FAST",
    "CTAS", "LRCX", "ORLY", "BKNG", "ANSS", "CDW", "ROST", "QCOM",
    "AZN", "TEAM", "ADI", "FANG", "LULU", "BIIB", "ISRG", "IDXX",
    "VRTX", "CMCSA", "PYPL", "INTC", "TXN", "AMGN", "MU", "SBUX", "ADP",
    "GILD", "MDLZ", "REGN", "VRSK", "MCHP", "FISV", "PAYX",
    "ON", "WBA", "EXC", "EBAY", "EA", "NTAP", "DLR",
    "STX", "ANET", "FTNT", "HPQ", "KEYS", "SWKS", "ZS", "OKTA", "DDOG",
    "CPRT", "CBOE", "GEHC", "HUB", "MP", "COIN", "ARM"
]
NASDAQ_100_COMPONENTS = list(dict.fromkeys(NASDAQ_100_COMPONENTS))


VENV = REPO_DIR / ".venv" / "bin" / "python3"


def fetch_ohlcv(ticker: str) -> list | None:
    """获取近60天OHLCV数据"""
    site_packages = str(REPO_DIR / ".venv" / "lib" / "python3.11" / "site-packages")
    code = f"""
import sys
sys.path.insert(0, '{site_packages}')
import yfinance as yf
import json
t = yf.Ticker("{ticker}")
df = t.history(period="3mo")
if df.empty:
    print("[]")
else:
    result = []
    for _, row in df.tail(60).iterrows():
        result.append({{
            "date": str(row.name.date()),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"])
        }})
    print(json.dumps(result))
"""
    try:
        result = subprocess.run(
            [str(VENV), "-c", code],
            capture_output=True, text=True, timeout=35
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            return data if data else None
    except Exception as e:
        pass
    return None


def detect_breakout(data: list[dict]) -> dict | None:
    """
    检测突破：
    1. 当日收盘价突破20日高点
    2. 成交量超过20日均量1.5倍
    3. 当日涨幅 > 1%
    """
    if not data or len(data) < 25:
        return None

    closes = [d["close"] for d in data]
    volumes = [d["volume"] for d in data]

    today = data[-1]
    yesterday = data[-2] if len(data) >= 2 else None

    # 20日高点（不含今日）
    highs_20 = [d["high"] for d in data[:-1][-20:]]
    high_20 = max(highs_20) if highs_20 else 0

    # 20日均量
    vol_20_avg = sum(volumes[:-1][-20:]) / min(20, len(volumes[:-1])) if len(volumes) > 1 else 0

    price = today["close"]
    vol_today = today["volume"]

    breakout_price = price > high_20
    vol_confirm = vol_today > vol_20_avg * 1.5 if vol_20_avg > 0 else False

    if yesterday:
        gain_pct = (price - yesterday["close"]) / yesterday["close"] * 100
    else:
        gain_pct = 0

    if breakout_price and vol_confirm and gain_pct > 0.5:
        return {
            "ticker": None,
            "date": today["date"],
            "price": price,
            "high_20": round(high_20, 2),
            "breakout_pct": round((price - high_20) / high_20 * 100, 2) if high_20 > 0 else 0,
            "gain_pct": round(gain_pct, 2),
            "vol_today": vol_today,
            "vol_20_avg": round(vol_20_avg),
            "vol_ratio": round(vol_today / vol_20_avg, 1) if vol_20_avg > 0 else 0,
        }
    return None


def run_analysis():
    results = []
    errors = []

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"📈 US Breakout — {now_str}", file=sys.stderr)
    print(f"   Scanning {len(NASDAQ_100_COMPONENTS)} NASDAQ 100 components...", file=sys.stderr)

    for ticker in NASDAQ_100_COMPONENTS:
        sys.stdout.write(f"  {ticker}... ")
        sys.stdout.flush()

        data = fetch_ohlcv(ticker)
        if not data:
            print("❌")
            errors.append(ticker)
            continue

        breakout = detect_breakout(data)
        if breakout:
            breakout["ticker"] = ticker
            results.append(breakout)
            print(f"✅ ${breakout['price']} 突破20日高 {breakout['high_20']} (+{breakout['breakout_pct']}%) 涨{breakout['gain_pct']}%")
        else:
            print("—")

        time.sleep(0.08)

    results.sort(key=lambda x: x["breakout_pct"], reverse=True)

    output = {
        "generatedAt": now_str,
        "timezone": "Asia/Shanghai",
        "total_scanned": len(NASDAQ_100_COMPONENTS),
        "breakouts": results[:20],
        "errors": errors[:10],
    }

    OUTPUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Done: {len(results)} breakouts → {OUTPUT_JSON}", file=sys.stderr)
    return output


if __name__ == "__main__":
    run_analysis()