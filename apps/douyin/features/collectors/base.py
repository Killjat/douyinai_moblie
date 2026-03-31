"""
采集器基类 - 定义采集接口，所有内容类型的采集器都继承此类。

使用方式：
    collector = VideoCollector(client, max_comments=10)
    item, ok = collector.collect(item, nodes)
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any


class BaseCollector(ABC):
    """
    采集器抽象基类。

    子类需实现：
    - content_type: 内容类型标识（如 "video"、"image"、"product"）
    - collect(): 进入详情页并采集，返回 (item, 是否成功)
    """

    content_type: str = "unknown"

    def __init__(self, client, **kwargs):
        self.client = client

    @abstractmethod
    def collect(self, item: Dict[str, Any], nodes: List[Dict]) -> Tuple[Dict[str, Any], bool]:
        """
        进入内容详情页，采集完整数据。

        Args:
            item: 列表页已解析的基础字段（title、nickname 等）
            nodes: 当前页面节点（用于定位点击目标）

        Returns:
            (enriched_item, success): 补充了详情字段的 item，以及是否成功进入详情
        """
