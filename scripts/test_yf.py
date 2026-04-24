#!/usr/bin/env python3
"""Test yfinance via subprocess with multiline code"""
import subprocess
import json
from pathlib import Path

code = """
import yfinance as yf
import json
t = yf.Ticker("AAPL")
df = t.history(period="5d")
print(df.tail(2))
print("len:", len(df))
"""

result = subprocess.run(
    ["python3", "-c", code],
    capture_output=True, text=True, timeout=20
)
print("stdout:", result.stdout[-500:] if result.stdout else "")
print("stderr:", result.stderr[-300:] if result.stderr else "")