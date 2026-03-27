"""
直播间数据采集功能模块（第一版）

已实现：
- 主播昵称（identifier: user_name）
- 在线人数（identifier: oke）
- 弹幕列表（identifier: /text，label 以 \u200e* 开头）

待实现（见 live.md TODO 章节）：
- 直播标题：弹窗遮挡，需调研关闭弹窗后的节点
- 直播分类/标签：未找到对应节点
- 人气榜前10：hittable=False，需调研点击方式
"""
import re
import html
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from loguru import logger
from apps.douyin.client import DouyinClient, PAGE_SIGNATURES


# ------------------------------------------------------------------
# 数据结构
# ------------------------------------------------------------------

@dataclass
class DanmakuItem:
    user: str       # 用户昵称（脱敏后如 "富***"）
    content: str    # 弹幕内容


@dataclass
class LiveInfo:
    anchor_name: str = ""               # 主播昵称
    title: str = ""                     # 直播标题（待实现）
    viewer_count: str = ""              # 在线人数原始文本
    category: str = ""                  # 直播分类（待实现）
    rank: List[Dict] = field(default_factory=list)   # 人气榜（待实现）
    danmaku: List[DanmakuItem] = field(default_factory=list)  # 当前可见弹幕
    collected_at: str = ""


# 直播间页面特征：有"礼物"按钮 + "说点什么"输入框
_IS_LIVE = lambda nodes: (
    any(n.get("label", "").strip() == "礼物" for n in nodes) and
    any("说点什么" in n.get("label", "") for n in nodes)
)


class LiveFeature:
    """直播间数据采集"""

    def __init__(self, client: DouyinClient):
        self.client = client

    def collect(self) -> LiveInfo:
        """采集当前直播间信息。调用前请确保手机已在直播间内。"""
        try:
            self.client.ensure_open()

            # 等待直播间页面就绪
            nodes = self.client.wait_for_page(_IS_LIVE, timeout=15, desc="直播间")
            return self._parse(nodes)
        except Exception as e:
            logger.error(f"采集直播间信息失败: {e}")
            return LiveInfo()
        finally:
            self.client.return_to_feed()

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------

    def _parse(self, nodes: List[Dict]) -> LiveInfo:
        info = LiveInfo(collected_at=datetime.now(timezone.utc).isoformat())

        for node in nodes:
            label = node.get("label", "").strip()
            identifier = node.get("identifier", "")
            if not label:
                continue

            # 主播昵称
            if "user_name" in identifier and not info.anchor_name:
                info.anchor_name = label
                logger.info(f"主播: {label}")

            # 在线人数
            elif identifier.endswith("oke") and re.match(r'^[\d.]+[万千]?$', label):
                info.viewer_count = label
                logger.info(f"在线人数: {label}")

            # 弹幕（label 以零宽字符 + * 开头）
            elif label.startswith("\u200e*") and "id/text" in identifier:
                dm = self._parse_danmaku(label)
                if dm:
                    info.danmaku.append(dm)

        if not info.anchor_name:
            logger.warning("未找到主播昵称")
        if not info.viewer_count:
            logger.warning("未找到在线人数")

        logger.success(
            f"直播间采集完成: 主播={info.anchor_name}, "
            f"在线={info.viewer_count}, 弹幕={len(info.danmaku)}条"
        )
        return info

    def _parse_danmaku(self, raw: str) -> Optional[DanmakuItem]:
        """解析弹幕节点 label，格式：\u200e* [*]* 用户名：内容 或 \u200e* 用户名 来了"""
        # 去掉开头的零宽字符和星号
        text = re.sub(r'^\u200e\*+\s*', '', raw).strip()
        text = html.unescape(text)

        if "：" in text:
            user, _, content = text.partition("：")
            return DanmakuItem(user=user.strip(), content=content.strip())
        elif text.endswith("来了"):
            user = text.replace("来了", "").strip()
            return DanmakuItem(user=user, content="[进入直播间]")
        return None
