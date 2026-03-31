"""
搜索接口 - SSE 实时推送 + search_id 缓存 + API 调用
"""
import json
import uuid
import asyncio
import time
from typing import AsyncGenerator, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

# 内存缓存：search_id -> {keyword, results, created_at, status}
_search_cache: Dict[str, Any] = {}


class SearchRequest(BaseModel):
    keyword: str
    count: int = 10
    max_comments: int = 5
    latest: bool = False
    topic: bool = False


async def _run_search(search_id: str, req: SearchRequest) -> AsyncGenerator[str, None]:
    import concurrent.futures
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    _search_cache[search_id] = {
        "search_id": search_id,
        "keyword": req.keyword,
        "results": [],
        "created_at": int(time.time()),
        "status": "running",
    }

    # 推送 search_id 给前端
    yield f"data: {json.dumps({'type': 'search_id', 'search_id': search_id}, ensure_ascii=False)}\n\n"

    def do_search():
        try:
            from apps.douyin.client import DouyinClient
            from apps.douyin.features.search import SearchFeature
            from apps.douyin.features.collectors.video import VideoCollector

            client = DouyinClient()

            class StreamingCollector(VideoCollector):
                def collect(self, item, nodes):
                    result, ok = super().collect(item, nodes)
                    _search_cache[search_id]["results"].append(result)
                    asyncio.run_coroutine_threadsafe(
                        queue.put({"type": "result", "data": result, "ok": ok}), loop
                    )
                    return result, ok

            collector = StreamingCollector(client, max_comments=req.max_comments)
            results = SearchFeature(client, collector=collector).search(
                req.keyword, count=req.count,
                latest=req.latest, topic=req.topic,
                max_comments=req.max_comments,
            )
            _search_cache[search_id]["status"] = "done"

            try:
                from apps.douyin.neo4j_exporter import Neo4jExporter
                exporter = Neo4jExporter()
                if exporter.connect():
                    with exporter:
                        exporter.export_feed(results)
            except Exception as e:
                print(f"[Neo4j] 写入失败: {e}")

            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "done", "total": len(results), "search_id": search_id}), loop
            )
        except Exception as e:
            _search_cache[search_id]["status"] = "error"
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "error", "msg": str(e)}), loop
            )

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    loop.run_in_executor(executor, do_search)

    while True:
        msg = await queue.get()
        yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
        if msg["type"] in ("done", "error"):
            break


@router.post("/stream")
async def search_stream(req: SearchRequest):
    """SSE 流式搜索，首条消息返回 search_id。"""
    search_id = uuid.uuid4().hex[:12]
    return StreamingResponse(
        _run_search(search_id, req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/result/{search_id}")
async def get_result(search_id: str):
    """通过 search_id 获取搜索结果（API 调用入口）。"""
    if search_id not in _search_cache:
        raise HTTPException(status_code=404, detail="search_id 不存在或已过期")
    cache = _search_cache[search_id]
    return {
        "search_id": search_id,
        "keyword": cache["keyword"],
        "status": cache["status"],
        "count": len(cache["results"]),
        "created_at": cache["created_at"],
        "results": cache["results"],
    }


@router.get("/history")
async def get_history():
    """获取所有搜索记录（不含结果详情）。"""
    return [
        {
            "search_id": v["search_id"],
            "keyword": v["keyword"],
            "status": v["status"],
            "count": len(v["results"]),
            "created_at": v["created_at"],
        }
        for v in sorted(_search_cache.values(), key=lambda x: -x["created_at"])
    ]


@router.post("/run")
async def search_run(req: SearchRequest):
    """普通搜索接口，等全部采集完再返回。"""
    import concurrent.futures
    search_id = uuid.uuid4().hex[:12]
    loop = asyncio.get_event_loop()

    def do_search():
        from apps.douyin.client import DouyinClient
        from apps.douyin.features.search import SearchFeature
        from apps.douyin.features.collectors.video import VideoCollector
        client = DouyinClient()
        collector = VideoCollector(client, max_comments=req.max_comments)
        return SearchFeature(client, collector=collector).search(
            req.keyword, count=req.count,
            latest=req.latest, topic=req.topic,
            max_comments=req.max_comments,
        )

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    results = await loop.run_in_executor(executor, do_search)

    _search_cache[search_id] = {
        "search_id": search_id, "keyword": req.keyword,
        "results": results, "created_at": int(time.time()), "status": "done",
    }

    try:
        from apps.douyin.neo4j_exporter import Neo4jExporter
        exporter = Neo4jExporter()
        if exporter.connect():
            with exporter:
                exporter.export_feed(results)
    except Exception as e:
        print(f"[Neo4j] 写入失败: {e}")

    return {"search_id": search_id, "keyword": req.keyword, "count": len(results), "results": results}
