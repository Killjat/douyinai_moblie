"""
搜索接口 - SSE 实时推送每条采集结果
"""
import json
import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


class SearchRequest(BaseModel):
    keyword: str
    count: int = 10
    max_comments: int = 5
    latest: bool = False
    topic: bool = False


async def _run_search(req: SearchRequest) -> AsyncGenerator[str, None]:
    """在线程池里跑同步搜索，每采集完一条通过 SSE 推送。"""
    import concurrent.futures
    loop = asyncio.get_event_loop()

    queue: asyncio.Queue = asyncio.Queue()

    def do_search():
        try:
            from apps.douyin.client import DouyinClient
            from apps.douyin.features.search import SearchFeature
            from apps.douyin.features.collectors.video import VideoCollector

            client = DouyinClient()

            # 包装 collector，每采集完一条放入队列
            class StreamingCollector(VideoCollector):
                def collect(self, item, nodes):
                    result, ok = super().collect(item, nodes)
                    asyncio.run_coroutine_threadsafe(
                        queue.put({"type": "result", "data": result, "ok": ok}),
                        loop
                    )
                    return result, ok

            collector = StreamingCollector(client, max_comments=req.max_comments)
            results = SearchFeature(client, collector=collector).search(
                req.keyword,
                count=req.count,
                latest=req.latest,
                topic=req.topic,
                max_comments=req.max_comments,
            )
            # 写入 Neo4j
            try:
                from apps.douyin.neo4j_exporter import Neo4jExporter
                exporter = Neo4jExporter()
                if exporter.connect():
                    with exporter:
                        exporter.export_feed(results)
            except Exception as neo4j_err:
                print(f"[Neo4j] 写入失败: {neo4j_err}")
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "done", "total": len(results)}), loop
            )
        except Exception as e:
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
    """SSE 流式搜索，每采集完一条视频实时推送。"""
    return StreamingResponse(
        _run_search(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/run")
async def search_run(req: SearchRequest):
    """普通搜索，等全部采集完再返回（适合 API 调用）。"""
    from apps.douyin.client import DouyinClient
    from apps.douyin.features.search import SearchFeature
    from apps.douyin.features.collectors.video import VideoCollector
    import concurrent.futures

    loop = asyncio.get_event_loop()

    def do_search():
        client = DouyinClient()
        collector = VideoCollector(client, max_comments=req.max_comments)
        return SearchFeature(client, collector=collector).search(
            req.keyword, count=req.count,
            latest=req.latest, topic=req.topic,
            max_comments=req.max_comments,
        )

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    results = await loop.run_in_executor(executor, do_search)

    # 写入 Neo4j
    try:
        from apps.douyin.neo4j_exporter import Neo4jExporter
        exporter = Neo4jExporter()
        if exporter.connect():
            with exporter:
                exporter.export_feed(results)
    except Exception as e:
        print(f"[Neo4j] 写入失败: {e}")

    return {"keyword": req.keyword, "count": len(results), "results": results}
