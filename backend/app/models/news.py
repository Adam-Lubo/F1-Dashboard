from pydantic import BaseModel


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    published_at: str
    summary: str | None = None
