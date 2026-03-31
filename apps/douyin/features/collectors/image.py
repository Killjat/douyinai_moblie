"""
图文采集器 - 进入图文详情，采集图片、文案、评论。
"""
import time
from typing import Dict, List, Tuple, Any
from loguru import logger
from apps.douyin.features.collectors.base import BaseCollector


class ImageCollector(BaseCollector):

    content_type = "image"

    def __init__(self, client, max_comments: int = 100, **kwargs):
        super().__init__(client)
        self.max_comments = max_comments

    def collect(self, item: Dict[str, Any], nodes: List[Dict]) -> Tuple[Dict[str, Any], bool]:
        """进入图文详情，采集图片和评论。"""
        # TODO: 实现图文采集逻辑
        logger.info(f"图文采集（待实现）: {item.get('title', '')[:40]}")
        item["comments"] = []
        item["images"] = []
        return item, False
