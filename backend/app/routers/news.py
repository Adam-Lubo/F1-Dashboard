from fastapi import APIRouter
from ..main import cache
from ..models.news import NewsItem
from ..services import news_client

router = APIRouter()


@router.get("/news", response_model=list[NewsItem])
def get_news():
    cached = cache.get("news")
    if cached is not None:
        return [NewsItem(**item) for item in cached]
    items = news_client.fetch_all()
    cache.set("news", [i.model_dump() for i in items], ttl_seconds=900)
    return items
