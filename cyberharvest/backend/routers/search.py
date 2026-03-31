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


# ------------------------------------------------------------------
# 两步采集：先扫描列表，用户选择后再采集详情
# ------------------------------------------------------------------

@router.post("/scan")
async def search_scan(req: SearchRequest):
    """第一步：快速扫描列表，返回 nickname+title，不进入视频。"""
    import concurrent.futures
    scan_id = uuid.uuid4().hex[:12]
    loop = asyncio.get_event_loop()

    def do_scan():
        from apps.douyin.client import DouyinClient
        from apps.douyin.features.search import SearchFeature
        client = DouyinClient()
        return SearchFeature(client).scan_list(
            req.keyword, count=req.count, latest=req.latest
        )

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    items = await loop.run_in_executor(executor, do_scan)

    # 缓存扫描结果，供后续 collect 使用
    _search_cache[scan_id] = {
        "search_id": scan_id, "keyword": req.keyword,
        "results": items, "created_at": int(time.time()), "status": "scanned",
    }
    return {"scan_id": scan_id, "keyword": req.keyword, "count": len(items), "items": items}


class CollectRequest(BaseModel):
    scan_id: str
    titles: list  # 用户选中的 title 列表
    max_comments: int = 5


async def _run_collect(req: CollectRequest) -> AsyncGenerator[str, None]:
    """对用户选中的视频进行详情采集，SSE 实时推送。"""
    import concurrent.futures

    if req.scan_id not in _search_cache:
        yield f"data: {json.dumps({'type': 'error', 'msg': 'scan_id 不存在'})}\n\n"
        return

    cache = _search_cache[req.scan_id]
    all_items = cache["results"]
    selected = [i for i in all_items if i.get("title", "").strip() in req.titles]

    collect_id = uuid.uuid4().hex[:12]
    _search_cache[collect_id] = {
        "search_id": collect_id, "keyword": cache["keyword"],
        "results": [], "created_at": int(time.time()), "status": "running",
    }
    yield f"data: {json.dumps({'type': 'search_id', 'search_id': collect_id}, ensure_ascii=False)}\n\n"

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def do_collect():
        try:
            from apps.douyin.client import DouyinClient
            from apps.douyin.features.search import SearchFeature
            from apps.douyin.features.collectors.video import VideoCollector

            client = DouyinClient()
            client.ensure_open()
            feed_nodes = client.navigate_to_feed()
            sf = SearchFeature(client)
            sf._keyword = cache["keyword"]
            if not sf._navigate_to_search(cache["keyword"], feed_nodes):
                asyncio.run_coroutine_threadsafe(
                    queue.put({"type": "error", "msg": "无法进入搜索结果页"}), loop)
                return
            sf._switch_to_video_tab()

            collector = VideoCollector(client, max_comments=req.max_comments)
            nodes = client.get_nodes()
            results = []

            for item in selected:
                detailed, ok = collector.collect(item, nodes)
                detailed["search_keyword"] = cache["keyword"]
                _search_cache[collect_id]["results"].append(detailed)
                asyncio.run_coroutine_threadsafe(
                    queue.put({"type": "result", "data": detailed, "ok": ok}), loop)
                nodes = client.get_nodes()  # 刷新节点
                results.append(detailed)

            _search_cache[collect_id]["status"] = "done"
            client.return_to_feed()

            try:
                from apps.douyin.neo4j_exporter import Neo4jExporter
                exporter = Neo4jExporter()
                if exporter.connect():
                    with exporter:
                        exporter.export_feed(results)
            except Exception as e:
                print(f"[Neo4j] 写入失败: {e}")

            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "done", "total": len(results), "search_id": collect_id}), loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "error", "msg": str(e)}), loop)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    loop.run_in_executor(executor, do_collect)

    while True:
        msg = await queue.get()
        yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
        if msg["type"] in ("done", "error"):
            break


@router.post("/collect")
async def search_collect(req: CollectRequest):
    """第二步：对用户选中的视频采集详情，SSE 实时推送。"""
    return StreamingResponse(
        _run_collect(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
