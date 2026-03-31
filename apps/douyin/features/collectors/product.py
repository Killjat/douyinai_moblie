"""
商品采集器 - 进入商品详情，采集价格、销量、评价等信息。
"""
import time
from typing import Dict, List, Tuple, Any
from loguru import logger
from apps.douyin.features.collectors.base import BaseCollector


class ProductCollector(BaseCollector):

    content_type = "product"

    def __init__(self, client, **kwargs):
        super().__init__(client)

    def collect(self, item: Dict[str, Any], nodes: List[Dict]) -> Tuple[Dict[str, Any], bool]:
        """进入商品详情，采集商品信息。"""
        # TODO: 实现商品采集逻辑
        logger.info(f"商品采集（待实现）: {item.get('title', '')[:40]}")
        item["price"] = ""
        item["sales"] = ""
        item["rating"] = ""
        return item, False
