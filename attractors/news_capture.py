"""Daily live-headline snapshotter. Run via `attractors capture-news` (or
cron). Captures top headlines from general-news RSS feeds into
data/news/<YYYY-MM-DD>.json — the replay corpus for the news tool."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import feedparser

from attractors.config import DATA_DIR

FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
]
PER_FEED = 6


def capture(news_dir: Path | None = None, when: date | None = None) -> Path:
    news_dir = news_dir or DATA_DIR / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    today = (when or date.today()).isoformat()
    headlines: list[str] = []
    sources: dict[str, int] = {}
    for name, url in FEEDS:
        try:
            feed = feedparser.parse(url)
            titles = [e.title.strip() for e in feed.entries[:PER_FEED]
                      if getattr(e, "title", "").strip()]
        except Exception:
            titles = []
        sources[name] = len(titles)
        headlines.extend(titles)
    if not headlines:
        raise RuntimeError("no headlines captured from any feed")
    path = news_dir / f"{today}.json"
    path.write_text(json.dumps(
        {"date": today, "headlines": headlines, "sources": sources},
        indent=2, ensure_ascii=False))
    return path
