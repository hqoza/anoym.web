import asyncio
import os
import re
from pathlib import Path

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse

BASE = Path(__file__).parent / "static"
BRAVE_KEY = os.getenv("BRAVE_API_KEY")  # необязательно

app = FastAPI(title="Web Search")


def clean(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


async def brave(q: str, n: int):
    if not BRAVE_KEY:
        return []
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": q, "count": n},
            headers={"X-Subscription-Token": BRAVE_KEY, "Accept": "application/json"},
        )
        r.raise_for_status()
    return [
        {
            "title": clean(x.get("title")),
            "url": x["url"],
            "snippet": clean(x.get("description")),
            "source": "Brave",
        }
        for x in r.json().get("web", {}).get("results", [])
    ]


def ddg_sync(q: str, n: int):
    from ddgs import DDGS

    return [
        {
            "title": x.get("title", ""),
            "url": x["href"],
            "snippet": x.get("body", ""),
            "source": "DuckDuckGo",
        }
        for x in DDGS().text(q, max_results=n)
    ]


async def ddg(q: str, n: int):
    return await asyncio.to_thread(ddg_sync, q, n)


@app.get("/search")
async def search(q: str = Query(..., min_length=1), limit: int = 10):
    batches = await asyncio.gather(
        brave(q, limit), ddg(q, limit), return_exceptions=True
    )
    lists = [b for b in batches if isinstance(b, list)]
    results, seen = [], set()
    for i in range(limit):
        for lst in lists:
            if i < len(lst) and lst[i]["url"] not in seen:
                seen.add(lst[i]["url"])
                results.append(lst[i])
    return {"query": q, "count": len(results), "results": results}


@app.get("/manifest.json")
async def manifest():
    return FileResponse(BASE / "manifest.json", media_type="application/manifest+json")


@app.get("/")
async def index():
    return FileResponse(BASE / "index.html")
