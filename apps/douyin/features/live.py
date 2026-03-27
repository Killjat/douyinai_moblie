"""
直播间数据采集功能模块

已实现：
- 主播昵称（resource-id: user_name）
- 本场点赞数（resource-id: auh，解析 "1.1万本场点赞"）
- 在线人数（resource-id: oke）
- 当前在线观众昵称列表（右上角头像区，无 resource-id，靠坐标范围识别）
- 弹幕列表（resource-id: text，label 以 \u200e* 开头）
- 礼物通知（从弹幕中识别送礼消息）

待实现（见 live.md TODO）：
- 直播标题 / 分类：仅在列表页预览卡片存在，直播间内无此节点
- 打赏榜单：榜单面板为 WebView，accessibility tree 无法获取
"""
import re
import html
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from loguru import logger
from apps.douyin.client import DouyinClient


# ------------------------------------------------------------------
# 数据结构
# ------------------------------------------------------------------

@dataclass
class DanmakuItem:
    user: str
    content: str
    is_gift: bool = False       # 是否为礼物通知


@dataclass
class LiveInfo:
    nickname: str = ""                                       # 主播昵称（对齐 User.nickname）
    total_likes: str = ""                                    # 本场点赞数，如 "1.1万"
    viewer_count: str = ""                                   # 当前在线人数
    top_viewers: List[str] = field(default_factory=list)    # 右上角在线观众昵称（前3名）
    danmaku: List[DanmakuItem] = field(default_factory=list)
    gifts: List[DanmakuItem] = field(default_factory=list)
    title: str = ""
    category: str = ""
    collected_at: str = ""


# 直播间页面特征
_IS_LIVE = lambda nodes: (
    any(n.get("label", "").strip() == "礼物" for n in nodes) and
    any("说点什么" in n.get("label", "") for n in nodes)
)

# 右上角观众头像区坐标范围（x: 630~900, y: 100~280）
_VIEWER_X_MIN, _VIEWER_X_MAX = 630, 900
_VIEWER_Y_MIN, _VIEWER_Y_MAX = 100, 280


class LiveFeature:
    """直播间数据采集。调用前请确保手机已在直播间内。"""

    def __init__(self, client: DouyinClient):
        self.client = client

    def collect(self) -> LiveInfo:
        """采集当前直播间完整信息"""
        try:
            self.client.ensure_open()
            nodes = self.client.wait_for_page(_IS_LIVE, timeout=30, desc="直播间")
            return self._parse(nodes)
        except Exception as e:
            logger.error(f"采集直播间信息失败: {e}")
            return LiveInfo()
        finally:
            try:
                self.client.return_to_feed()
            except Exception as e:
                logger.warning(f"回到推荐页失败: {e}")

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------

    def _parse(self, nodes: List[Dict]) -> LiveInfo:
        info = LiveInfo(collected_at=datetime.now(timezone.utc).isoformat())

        for node in nodes:
            label = node.get("label", "").strip()
            identifier = node.get("identifier", "")
            rect = node.get("rect", {})
            if not label:
                continue

            # 主播昵称
            if "user_name" in identifier and not info.nickname:
                info.nickname = label
                logger.info(f"主播: {label}")

            # 本场点赞（格式："JT-0011.2万本场点赞"，resource-id: auh）
            # 点赞数紧贴"本场点赞"前，格式为 数字+可选单位
            elif identifier.endswith("auh") and "本场点赞" in label and not info.total_likes:
                m = re.search(r'(\d[\d.]*[万千]?)本场点赞', label)
                if m:
                    info.total_likes = m.group(1)
                    logger.info(f"本场点赞: {info.total_likes}")

            # 在线人数
            elif identifier.endswith("oke") and re.match(r'^[\d.]+[万千]?$', label):
                info.viewer_count = label
                logger.info(f"在线人数: {label}")

            # 右上角在线观众（靠坐标范围识别，无 resource-id）
            elif (not identifier and node.get("hittable") and label
                  and not any(k in label for k in ["按钮", "关注", "关闭", "榜", "广场", "Banner"])
                  and len(label) < 20):
                x = rect.get("x", 0)
                y = rect.get("y", 0)
                if _VIEWER_X_MIN <= x <= _VIEWER_X_MAX and _VIEWER_Y_MIN <= y <= _VIEWER_Y_MAX:
                    if label not in info.top_viewers:
                        info.top_viewers.append(label)
                        logger.info(f"在线观众: {label}")

            # 弹幕 / 礼物通知
            elif label.startswith("\u200e*") and "id/text" in identifier:
                dm = self._parse_danmaku(label)
                if dm:
                    if dm.is_gift:
                        info.gifts.append(dm)
                    else:
                        info.danmaku.append(dm)

        if not info.nickname:
            logger.warning("未找到主播昵称")
        if not info.viewer_count:
            logger.warning("未找到在线人数")

        logger.success(
            f"采集完成: 主播={info.nickname}, 点赞={info.total_likes}, "
            f"在线={info.viewer_count}, 观众={len(info.top_viewers)}人, "
            f"弹幕={len(info.danmaku)}条, 礼物={len(info.gifts)}条"
        )
        return info

    def _parse_danmaku(self, raw: str) -> Optional[DanmakuItem]:
        """解析弹幕 label"""
        text = re.sub(r'^\u200e\*+\s*', '', raw).strip()
        text = html.unescape(text)

        # 礼物通知：送了礼物 / 分享了直播 / 送XX
        gift_patterns = ["送了", "送出", "分享了直播", "送小心心", "赠送"]
        if any(p in text for p in gift_patterns):
            user = text.split("：")[0].strip() if "：" in text else text
            return DanmakuItem(user=user, content=text, is_gift=True)

        if "：" in text:
            user, _, content = text.partition("：")
            return DanmakuItem(user=user.strip(), content=content.strip())
        elif text.endswith("来了"):
            return DanmakuItem(user=text.replace("来了", "").strip(), content="[进入直播间]")
        return None
