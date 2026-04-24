import feedparser
from ..models.news import NewsItem

RSS_FEEDS = [
    ("The Race",       "https://the-race.com/feed/"),
    ("Autosport",      "https://www.autosport.com/rss/f1/news/"),
    ("Motorsport.com", "https://www.motorsport.com/rss/f1/news/"),
]


def _parse_entry(entry: dict, source: str) -> NewsItem | None:
    title = entry.get("title", "").strip()
    url = entry.get("link", "").strip()
    if not title or not url:
        return None
    published = entry.get("published", entry.get("updated", ""))
    summary = entry.get("summary", None)
    if summary:
        summary = summary[:300]
    return NewsItem(title=title, url=url, source=source,
                    published_at=published, summary=summary)


def fetch_all(max_per_feed: int = 5) -> list[NewsItem]:
    items: list[NewsItem] = []
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                item = _parse_entry(entry, source)
                if item:
                    items.append(item)
        except Exception:
            pass
    return items
