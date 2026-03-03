#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_DIR = Path("/Users/lijiaolong/.openclaw/workspace/daynews")
DOCS_DIR = REPO_DIR / "docs"
CACHE_PATH = REPO_DIR / ".cache" / "rss_items.json"
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Simple, free, no-key feeds. (Some publishers may change/limit; we keep it best-effort.)
FEEDS: list[tuple[str, str]] = [
    ("YahooFinance-Markets", "https://finance.yahoo.com/news/rssindex"),
    ("Investing-Markets", "https://www.investing.com/rss/news_25.rss"),
    ("CNBC-Top", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("CNBC-World", "https://www.cnbc.com/id/100727362/device/rss/rss.html"),
    ("CNBC-Tech", "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
    ("MarketWatch-Top", "https://feeds.marketwatch.com/marketwatch/topstories"),
    ("MarketWatch-Markets", "https://feeds.marketwatch.com/marketwatch/marketpulse"),
    ("TheVerge-AI", "https://www.theverge.com/artificial-intelligence/rss/index.xml"),
]


@dataclass
class Item:
    source: str
    title: str
    url: str
    published: dt.datetime | None
    summary: str


def _now_bjt() -> dt.datetime:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))


def _clean(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _hash_key(url: str, title: str) -> str:
    return hashlib.sha256((url.strip() + "\n" + title.strip()).encode("utf-8")).hexdigest()


def _parse_rfc822(s: str) -> dt.datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        from email.utils import parsedate_to_datetime

        d = parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d
    except Exception:
        return None


def _parse_iso(s: str) -> dt.datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        # handle Z
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None


def _extract_items(feed_name: str, xml_text: str) -> list[Item]:
    out: list[Item] = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return out

    # RSS 2.0
    for it in root.findall(".//item"):
        title = _clean((it.findtext("title") or ""))
        url = (it.findtext("link") or "").strip()
        desc = _clean((it.findtext("description") or ""))
        pub = _parse_rfc822(it.findtext("pubDate") or "")
        if title and url:
            out.append(Item(feed_name, title, url, pub, desc))

    # Atom
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
    }
    for entry in root.findall(".//atom:entry", ns):
        title = _clean((entry.findtext("atom:title", default="", namespaces=ns) or ""))
        url = ""
        for l in entry.findall("atom:link", ns):
            rel = (l.attrib.get("rel") or "").lower()
            if rel in ("", "alternate"):
                url = l.attrib.get("href") or url
        summary = _clean((entry.findtext("atom:summary", default="", namespaces=ns) or ""))
        updated = _parse_iso(entry.findtext("atom:updated", default="", namespaces=ns) or "")
        if title and url:
            out.append(Item(feed_name, title, url, updated, summary))

    return out


def fetch_all(hours: int = 36) -> dict[str, Any]:
    now = _now_bjt()
    cutoff = now.astimezone(dt.timezone.utc) - dt.timedelta(hours=hours)

    items: dict[str, dict[str, Any]] = {}

    for name, url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DayNewsRSS/1.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                xml_text = resp.read().decode("utf-8", errors="replace")
        except Exception:
            continue

        for it in _extract_items(name, xml_text):
            pub = it.published
            if pub is None:
                # treat as recent-ish
                pub = now.astimezone(dt.timezone.utc)
            if pub.astimezone(dt.timezone.utc) < cutoff:
                continue
            k = _hash_key(it.url, it.title)
            if k in items:
                continue
            items[k] = {
                "source": it.source,
                "headline": it.title,
                "summary": it.summary,
                "url": it.url,
                "datetime": int(pub.astimezone(dt.timezone.utc).timestamp()),
                "related": "RSS",
            }

    # sort desc
    arr = sorted(items.values(), key=lambda x: int(x.get("datetime") or 0), reverse=True)

    payload = {
        "generatedAtBJT": now.strftime("%Y-%m-%d %H:%M:%S"),
        "rangeHours": hours,
        "count": len(arr),
        "items": arr,
    }
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    fetch_all()
