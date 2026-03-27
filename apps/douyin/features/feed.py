"""
推荐视频流功能模块
- 扫描推荐视频：作者、标题、互动数据
- 抓取评论区
"""
import re
import time
from typing import Dict, List, Any
from loguru import logger
from apps.douyin.client import DouyinClient, PAGE_SIGNATURES


class FeedFeature:
    """推荐视频流相关功能"""

    def __init__(self, client: DouyinClient):
        self.client = client

    def scan(self, count: int = 5) -> List[Dict[str, Any]]:
        """扫描推荐视频流，获取每个视频的作者、标题、互动数据和评论"""
        try:
            self.client.ensure_open()
            self.client.navigate_to_feed()
        except Exception as e:
            logger.error(f"导航到推荐页失败: {e}")
            return []

        results = []
        for i in range(count):
            logger.info(f"扫描第 {i + 1}/{count} 个视频...")
            try:
                nodes = self.client.get_nodes()
                video_info = self._parse_video(nodes)
                logger.info(f"作者={video_info.get('author')}, 标题={video_info.get('title', '')[:20]}")
                video_info["comments"] = self._fetch_comments(nodes)
                results.append(video_info)
            except Exception as e:
                logger.warning(f"第 {i + 1} 个视频解析失败: {e}")
                results.append({"error": str(e)})

            if i < count - 1:
                logger.info("滑动到下一个视频...")
                self.client.adb.swipe(540, 1600, 540, 400, duration=300)
                time.sleep(2.5)

        logger.success(f"扫描完成，共获取 {len(results)} 个视频")
        self.client.return_to_feed()
        return results

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------

    def _parse_video(self, nodes: List[Dict]) -> Dict[str, Any]:
        info = {
            "author": "", "author_handle": "", "title": "",
            "likes": "", "comment_count": "", "shares": "", "music": "",
        }
        for node in nodes:
            label = node.get("label", "").strip()
            if not label:
                continue

            if label.startswith("@") and node.get("hittable"):
                info["author_handle"] = label
                info["author"] = label.lstrip("@")

            elif "展开" in label and len(label) > 10:
                info["title"] = label.replace(" 展开>", "").replace(" 展开", "").strip()

            elif re.match(r'^(未|已)点赞，喜欢', label):
                m = re.search(r'喜欢(\d+)', label)
                if m:
                    info["likes"] = m.group(1)

            elif label.startswith("评论") and re.search(r'\d+', label):
                m = re.search(r'评论(\d+)', label)
                if m:
                    info["comment_count"] = m.group(1)

            elif label.startswith("分享") and re.search(r'\d+', label):
                m = re.search(r'分享(\d+)', label)
                if m:
                    info["shares"] = m.group(1)

            elif label.startswith("音乐，"):
                info["music"] = label.replace("音乐，", "").replace("，按钮", "").strip()

        return info

    def _fetch_comments(self, nodes: List[Dict], max_comments: int = 10) -> List[Dict[str, Any]]:
        """打开评论区抓取评论，完成后关闭"""
        comment_btn = next(
            (n for n in nodes
             if n.get("hittable") and n.get("label", "").startswith("评论")
             and re.search(r'\d+', n.get("label", ""))),
            None
        )
        if not comment_btn:
            logger.info("无评论按钮（图片集或无评论）")
            return []

        self.client.device.press(comment_btn.get("ref"))
        try:
            comment_nodes = self.client.wait_for_page(
                PAGE_SIGNATURES["douyin_comments"], timeout=8, desc="评论区"
            )
        except TimeoutError:
            logger.warning("评论区加载超时")
            return []

        comments = self._parse_comments(comment_nodes, max_comments)

        close_node = next(
            (n for n in self.client.get_nodes() if n.get("label", "").strip() == "关闭"),
            None
        )
        if close_node:
            self.client.device.press(close_node.get("ref"))
            time.sleep(1)

        return comments

    def _parse_comments(self, nodes: List[Dict], max_comments: int = 10) -> List[Dict[str, Any]]:
        total_node = next((n for n in nodes if "条评论" in n.get("label", "")), None)
        total = total_node.get("label", "") if total_node else ""

        comments = []
        i = 0
        while i < len(nodes) and len(comments) < max_comments:
            label = nodes[i].get("label", "").strip()
            if (nodes[i].get("hittable") and label and len(label) < 25
                    and not any(k in label for k in ["按钮", "关闭", "搜索", "放大", "at", "表情", "插入", "发送", "回复", "展开", "作者", "都在搜"])
                    and "头像" not in label
                    and i + 1 < len(nodes)):
                next_label = nodes[i + 1].get("label", "").strip()
                if (len(next_label) > 5
                        and not re.match(r'^(昨天|今天|\d{4}|\d+月|\d+:\d+|·\s)', next_label)):
                    comments.append({"user": label, "content": next_label, "total_in_video": total})
                    i += 2
                    continue
            i += 1

        logger.info(f"解析到 {len(comments)} 条评论（共 {total}）")
        return comments
