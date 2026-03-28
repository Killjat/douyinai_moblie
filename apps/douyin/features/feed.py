"""
推荐视频流功能模块
- 扫描推荐视频：作者、标题、互动数据
- 抓取评论区
"""
import re
import time
from typing import Dict, List, Any, Optional, Set, Tuple
from loguru import logger
from apps.douyin.client import DouyinClient, PAGE_SIGNATURES


def _comment_count_candidates(nodes: List[Dict]) -> List[int]:
    """
    从快照里收集「总评论数」的多个候选（不同控件会拆成 6 / 65 等），取 max 更接近真实总数。
    覆盖：N条评论、共N条、侧栏「评论，N」等。
    """
    out: List[int] = []
    for n in nodes:
        lab = (n.get("label") or "").strip()
        if not lab:
            continue
        for m in re.finditer(r"(\d+)\s*条评论", lab):
            v = int(m.group(1))
            if 0 < v < 50_000_000:
                out.append(v)
        if "评论" in lab or "回复" in lab:
            m = re.search(r"共\s*(\d+)\s*条", lab)
            if m:
                v = int(m.group(1))
                if 0 < v < 50_000_000:
                    out.append(v)
        if "评论" in lab and "条评论" not in lab and re.search(r"\d", lab):
            m = re.search(r"评论[,，\s]*(\d+)(?:\s*$|[,，\s\u4e00-\u9fff]|[^\d])", lab)
            if m:
                v = int(m.group(1))
                if 0 < v < 50_000_000:
                    out.append(v)
    return out


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
                comments, panel_total = self._fetch_comments(nodes)
                video_info["comments"] = comments
                if panel_total:
                    video_info["comment_count"] = panel_total
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
        """
        字段命名与 ai_social_relationship 的 Neo4j Work 节点对齐：
          nickname      ← 视频作者（对齐 User.nickname）
          author_handle ← @句柄
          type          ← 视频类型（视频/图文）
          title         ← 视频标题
          likes         ← 点赞数（对齐 Work.likes）
          comment_count ← 评论数
          shares        ← 分享数
          music         ← 背景音乐
        注：work_id / url 手机端无法获取，需 Web 端补全
        """
        info = {
            "nickname": "", "author_handle": "",
            "type": "视频",   # 默认视频，图文时会覆盖
            "title": "",
            "likes": "", "comment_count": "", "shares": "", "music": "",
        }
        for node in nodes:
            label = node.get("label", "").strip()
            identifier = node.get("identifier", "")
            if not label:
                continue

            if label.startswith("@") and node.get("hittable"):
                info["author_handle"] = label
                info["nickname"] = label.lstrip("@")

            elif "展开" in label and len(label) > 10:
                info["title"] = label.replace(" 展开>", "").replace(" 展开", "").strip()

            elif re.match(r'^(未|已)点赞，喜欢', label):
                m = re.search(r'喜欢(\d+)', label)
                if m:
                    info["likes"] = m.group(1)

            elif label.startswith("分享") and re.search(r'\d+', label):
                m = re.search(r'分享(\d+)', label)
                if m:
                    info["shares"] = m.group(1)

            elif label.startswith("音乐，"):
                info["music"] = label.replace("音乐，", "").replace("，按钮", "").strip()

            # 图文类型识别
            elif "图片" in label and "按钮" in label and "图片1" in label:
                info["type"] = "图文"

        cc = _comment_count_candidates(nodes)
        if cc:
            info["comment_count"] = str(max(cc))

        return info

    @staticmethod
    def _comment_key(c: Dict[str, Any]) -> Tuple[str, str]:
        return (c.get("user", ""), c.get("content", ""))

    def _fetch_comments(
        self, nodes: List[Dict], max_comments: int = 10
    ) -> Tuple[List[Dict[str, Any]], str]:
        """打开评论区抓取评论；返回 (评论列表, 面板标题解析出的总评论数字符串)。"""
        comment_btn = next(
            (n for n in nodes
             if n.get("hittable") and n.get("label", "").startswith("评论")
             and re.search(r'\d+', n.get("label", ""))),
            None
        )
        if not comment_btn:
            for n in nodes:
                if not n.get("hittable"):
                    continue
                lab = n.get("label", "").strip()
                if "评论" in lab and re.search(r"\d+", lab):
                    comment_btn = n
                    break
        if not comment_btn:
            logger.info("无评论按钮（图片集或无评论）")
            return [], ""

        self.client.device.press(comment_btn.get("ref"))
        try:
            comment_nodes = self.client.wait_for_page(
                PAGE_SIGNATURES["douyin_comments"], timeout=8, desc="评论区"
            )
        except TimeoutError:
            logger.warning("评论区加载超时")
            return [], ""

        panel_vals = _comment_count_candidates(comment_nodes)
        panel_total = str(max(panel_vals)) if panel_vals else ""

        comments = self._gather_comments_with_scroll(comment_nodes, max_comments)

        if panel_total:
            for c in comments:
                c["total_in_video"] = f"{panel_total}条评论"

        close_node = next(
            (n for n in self.client.get_nodes() if n.get("label", "").strip() == "关闭"),
            None
        )
        if close_node:
            self.client.device.press(close_node.get("ref"))
            time.sleep(1)

        return comments, panel_total

    def _gather_comments_with_scroll(self, initial_nodes: List[Dict], max_comments: int) -> List[Dict[str, Any]]:
        """多次快照 + 上滑，合并去重，最多 max_comments 条"""
        seen: Set[Tuple[str, str]] = set()
        merged: List[Dict[str, Any]] = []
        stagnant_rounds = 0
        max_rounds = 60 if max_comments > 20 else 8
        nodes = initial_nodes

        for _ in range(max_rounds):
            chunk = self._parse_comments(nodes, limit=None)
            before = len(seen)
            for c in chunk:
                k = self._comment_key(c)
                if k in seen or not k[0] or not k[1]:
                    continue
                seen.add(k)
                merged.append(c)
                if len(merged) >= max_comments:
                    logger.info(f"评论已凑满 {max_comments} 条")
                    return merged[:max_comments]
            if len(seen) == before:
                stagnant_rounds += 1
                if stagnant_rounds >= 4:
                    break
            else:
                stagnant_rounds = 0

            self.client.adb.swipe(540, 1500, 540, 700, duration=350)
            time.sleep(1.0)
            nodes = self.client.get_nodes()

        logger.info(f"评论采集结束: {len(merged)} 条（目标 {max_comments}）")
        return merged[:max_comments]

    def _parse_comments(self, nodes: List[Dict], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """limit=None 时解析当前快照中全部可识别评论对"""
        total_node = next((n for n in nodes if "条评论" in n.get("label", "")), None)
        total = total_node.get("label", "") if total_node else ""

        comments: List[Dict[str, Any]] = []
        i = 0
        while i < len(nodes) and (limit is None or len(comments) < limit):
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

        return comments
