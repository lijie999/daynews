#!/usr/bin/env python3
"""
A股日线突破检测 - 当日涨停股前50只
每天 09:00 和 21:00 运行
逻辑：涨停股中，突破盘整区间（20日高点+缩量整理）
"""
import json
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta

REPO_DIR = Path("/Users/lijiaolong/.openclaw/workspace/daynews")
OUTPUT_JSON = REPO_DIR / "docs" / "cn_breakout.json"
VENV = REPO_DIR / ".venv" / "bin" / "python3"


def fetch_cn_tickers() -> list[dict]:
    """获取A股当日涨停股票列表（前50只）使用akshare"""
    code = """
import sys
sys.path.insert(0, '/Users/lijiaolong/.openclaw/workspace/daynews/.venv/lib/python3.11/site-packages')
import akshare as ak
import json
try:
    df = ak.stock_zt_pool_em(date=datetime.now().strftime("%Y%m%d"))
    if df is not None and len(df) > 0:
        result = []
        for _, row in df.head(50).iterrows():
            result.append({
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "close": float(row.get("涨停价", 0))
            })
        print(json.dumps(result))
    else:
        print("[]")
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
"""
    try:
        result = subprocess.run(
            [str(VENV), "-c", code],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip() and not result.stdout.strip().startswith("Error"):
            data = json.loads(result.stdout.strip())
            return data if data else []
    except Exception as e:
        print(f"⚠️ akshare failed: {e}", file=sys.stderr)
    return []


def fetch_ohlcv_cn(code: str) -> list | None:
    """获取A股近60天OHLCV（使用yfinance .SZ/.SS）"""
    if code.startswith("6"):
        yf_code = f"{code}.SS"
    else:
        yf_code = f"{code}.SZ"

    site_packages = str(REPO_DIR / ".venv" / "lib" / "python3.11" / "site-packages")
    code_snippet = f"""
import sys
sys.path.insert(0, '{site_packages}')
import yfinance as yf
import json
import datetime
t = yf.Ticker("{yf_code}")
end = datetime.date.today()
start = end - datetime.timedelta(days=120)
df = t.history(start=start, end=end)
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
        result = subprocess.run([str(VENV), "-c", code_snippet],
                               capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            return data if data else None
    except Exception:
        pass
    return None


def detect_cn_breakout(data: list[dict]) -> dict | None:
    """
    A股突破检测：
    1. 今日涨幅 >= 9.8%（接近涨停）
    2. 突破20日高点
    3. 盘整特征：前5日振幅 < 15%，量能萎缩
    4. 今日量比 > 1.3
    """
    if not data or len(data) < 25:
        return None

    today = data[-1]
    prev_5 = data[-6:-1] if len(data) >= 6 else data[:-1]
    yesterday = data[-2] if len(data) >= 2 else None

    if not yesterday:
        return None

    # 20日高点（不含今日）
    highs_20 = [d["high"] for d in data[:-1][-20:]]
    high_20 = max(highs_20) if highs_20 else 0

    # 前5日振幅（盘整特征）
    ranges = [(d["high"] - d["low"]) / d["low"] * 100 for d in prev_5 if d["low"] > 0]
    avg_range = sum(ranges) / len(ranges) if ranges else 0

    # 前5日均量
    prev_vols = [d["volume"] for d in prev_5]
    prev_vol_avg = sum(prev_vols) / len(prev_vols) if prev_vols else 0

    vol_today = today["volume"]
    vol_ratio = vol_today / prev_vol_avg if prev_vol_avg > 0 else 0

    # 涨停价（昨收 * 1.1）
    zt_price = yesterday["close"] * 1.1
    near_zt = today["close"] >= zt_price * 0.998

    price = today["close"]
    breakout = price > high_20 and vol_ratio >= 1.3 and avg_range < 15

    if near_zt and breakout:
        return {
            "code": None,
            "name": None,
            "date": today["date"],
            "price": price,
            "zt_price": round(zt_price, 2),
            "high_20": round(high_20, 2),
            "breakout_pct": round((price - high_20) / high_20 * 100, 2) if high_20 > 0 else 0,
            "gain_pct": round((price - yesterday["close"]) / yesterday["close"] * 100, 2),
            "vol_ratio": round(vol_ratio, 1),
            "prev_range_pct": round(avg_range, 1),
        }
    return None


def run_analysis():
    print(f"📈 CN Breakout — {datetime.now().strftime('%Y-%m-%d %H:%M')}", file=sys.stderr)
    print("   Fetching A-share limit-up stocks...", file=sys.stderr)

    tickers = fetch_cn_tickers()
    print(f"   Found {len(tickers)} limit-up stocks", file=sys.stderr)

    results = []
    errors = []

    for item in tickers[:50]:
        code = item["code"]
        name = item["name"]
        sys.stdout.write(f"  {code} {name}... ")
        sys.stdout.flush()

        data = fetch_ohlcv_cn(code)
        if not data:
            print("❌")
            errors.append(f"{code}_{name}")
            continue

        breakout = detect_cn_breakout(data)
        if breakout:
            breakout["code"] = code
            breakout["name"] = name
            results.append(breakout)
            print(f"✅ 涨{breakout['gain_pct']}% 量比{breakout['vol_ratio']}x")
        else:
            print("—")

        time.sleep(0.1)

    results.sort(key=lambda x: x["vol_ratio"], reverse=True)

    output = {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "Asia/Shanghai",
        "total_found": len(tickers),
        "analyzed": min(len(tickers), 50),
        "breakouts": results[:20],
        "errors": errors[:10],
    }

    OUTPUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Done: {len(results)} breakouts → {OUTPUT_JSON}", file=sys.stderr)
    return output


if __name__ == "__main__":
    run_analysis()