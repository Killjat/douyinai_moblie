"""
搜索功能模块
- 搜索关键词，采集相关视频列表
- 支持切换到「话题」并进入话题详情页，采集该话题下的作品
- 支持滚动翻页，持续采集
"""
import re
import time
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger
from apps.douyin.client import DouyinClient
from apps.douyin.features.feed import FeedFeature


_BAD_AUTHOR_LABELS = frozenset({
    "填入搜索框", "搜索", "历史记录", "猜你想搜", "大家都在搜", "相关搜索",
    "综合", "视频", "用户", "直播", "话题", "商品",
    "进度条", "加载中", "缓冲", "失败", "重试",
})


def _looks_like_bad_author_nickname(text: str) -> bool:
    """列表解析时，标题后的短文案常被误当成作者（进度条、系统提示等）。"""
    if not text or text in _BAD_AUTHOR_LABELS:
        return True
    if text.startswith("抖音怎么") or text.startswith("点击查看"):
        return True
    if "可能认" in text and len(text) < 20:
        return True
    return False


def _is_search_results_page(nodes: List[Dict]) -> bool:
    """搜索结果页：顶部 Tab 或筛选条（不同版本文案略有差异）"""
    tabs = {
        "综合", "视频", "用户", "直播", "话题", "商品", "图文",
        "全部", "经验", "团购", "店铺",
    }
    for n in nodes:
        if n.get("label", "").strip() in tabs:
            return True
    # 无 Tab 文案时：常见「筛选」+ 多结果列表
    joined = "".join((n.get("label") or "") for n in nodes[:250])
    if "筛选" in joined and len(joined) > 80:
        return True
    return False


class SearchFeature:
    """关键词搜索，采集相关视频"""

    def __init__(self, client: DouyinClient):
        self.client = client
        self._keyword: str = ""
        self._topic_mode: bool = False
        self._max_comments: int = 100

    def search(
        self,
        keyword: str,
        count: int = 10,
        topic: bool = False,
        max_comments: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        搜索关键词，采集前 count 条视频。
        topic=True：进「话题」Tab 并打开匹配话题，再采话题下的作品。

        每条优先包含：title、likes、comment_count、comments（最多 max_comments 条）、nickname；
        另有 search_keyword；话题模式另有 topic 字段。
        """
        self._keyword = keyword
        self._topic_mode = topic
        self._max_comments = max(1, min(max_comments, 200))
        try:
            self.client.ensure_open()
            if not self._navigate_to_search(keyword):
                return []
            if topic:
                if not self._open_topic_page(keyword):
                    logger.error("未能进入话题详情，退回普通搜索结果采集")
                    self._topic_mode = False
            return self._collect(count)
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
        finally:
            self._keyword = ""
            self._topic_mode = False
            self._max_comments = 100
            self.client.return_to_feed()

    # ------------------------------------------------------------------
    # 导航
    # ------------------------------------------------------------------

    def _navigate_to_search(self, keyword: str) -> bool:
        """导航到搜索结果页"""
        # 先确保在推荐页（搜索按钮在推荐页顶部）
        try:
            nodes = self.client.navigate_to_feed()
        except Exception:
            nodes = self.client.get_nodes()

        # 找搜索按钮（推荐页右上角）
        search_btn = None
        for n in nodes:
            label = n.get("label", "").strip()
            if (n.get("hittable") and 
                (label == "搜索" or "搜索" in label)):
                search_btn = n
                logger.info(f"找到搜索按钮: {label}")
                break
        
        if not search_btn:
            logger.error("未找到搜索按钮，尝试使用坐标点击")
            # 尝试使用坐标点击搜索按钮（假设在右上角）
            self.client.adb.tap(900, 100)  # 调整坐标位置
            time.sleep(2)
        else:
            self.client.device.press(search_btn.get("ref"))
            time.sleep(1.0)

        # 在搜索页找历史记录或输入框
        nodes = self.client.get_nodes()

        # 优先点历史记录：先精确匹配关键词，否则选「包含关键词的最短」一条，避免点到长尾联想
        candidates: List[tuple] = []
        for n in nodes:
            if not n.get("hittable"):
                continue
            lab = n.get("label", "").strip()
            if keyword not in lab:
                continue
            if "填入搜索框" in lab or lab in _BAD_AUTHOR_LABELS:
                continue
            candidates.append((lab, n))
        history_node = None
        if candidates:
            exact = [(lab, n) for lab, n in candidates if lab == keyword]
            if exact:
                history_node = exact[0][1]
            else:
                candidates.sort(key=lambda x: len(x[0]))
                history_node = candidates[0][1]
        if history_node:
            logger.info(f"从历史记录点击: {history_node.get('label', '')!r}")
            self.client.device.press(history_node.get("ref"))
            time.sleep(0.8)
        else:
            # 找输入框输入（支持中文）
            input_node = next(
                (n for n in nodes if n.get("hittable") and "搜索" in n.get("label", "")),
                None
            )
            if input_node:
                self.client.device.press(input_node.get("ref"))
                time.sleep(1)  # 增加等待时间确保输入框激活
            
            # 先清除输入框（如果有内容）
            self.client.adb.press_key("KEYCODE_DEL")
            time.sleep(0.5)
            
            # 使用剪贴板输入中文
            try:
                import pyperclip
                pyperclip.copy(keyword)
                # 长按输入框调出粘贴选项
                self.client.adb.tap(500, 200)  # 假设输入框在屏幕上方
                time.sleep(0.5)
                self.client.adb.press_key("KEYCODE_PASTE")
                logger.info(f"已通过剪贴板输入: {keyword}")
            except ImportError:
                logger.warning("pyperclip未安装，尝试直接输入（仅支持英文）")
                self.client.adb.input_text(keyword)
            
            # 按回车键搜索
            self.client.adb.press_key("KEYCODE_ENTER")
            time.sleep(2)  # 增加等待时间确保搜索结果加载

        # 等待搜索结果页（snapshot 较慢，缩短轮询间隔、略放宽页面判定以减少空等）
        try:
            self.client.wait_for_page(
                _is_search_results_page,
                timeout=12,
                desc="搜索结果页",
                poll_interval=0.45,
            )
            logger.info(f"搜索结果已加载: {keyword}")
            return True
        except TimeoutError:
            logger.error("搜索结果页加载超时，尝试继续执行")
            return True

    def _ensure_topic_tab_visible(self) -> Optional[Dict]:
        """横向滑动 Tab 栏，直到出现可点的「话题」"""
        for _ in range(8):
            nodes = self.client.get_nodes()
            tab = self._find_topic_tab(nodes)
            if tab:
                return tab
            self.client.adb.swipe(720, 240, 80, 240, duration=320)
            time.sleep(0.6)
        return None

    def _open_topic_page(self, keyword: str) -> bool:
        """在搜索结果页点击「话题」Tab，再进入名称匹配的话题详情（作品列表）。"""
        time.sleep(1.2)
        nodes = self.client.get_nodes()

        topic_tab = self._ensure_topic_tab_visible()
        opened_topic_tab = topic_tab is not None
        if topic_tab:
            logger.info(f"点击话题 Tab: {topic_tab.get('label', '')!r}")
            self.client.device.press(topic_tab.get("ref"))
            time.sleep(2.5)
            nodes = self.client.get_nodes()
        else:
            logger.warning("未找到「话题」Tab，仅在综合结果中查找带播放量的话题行")

        row = self._pick_topic_row(nodes, keyword, strict_play_count=not opened_topic_tab)
        if not row:
            logger.error(f"未找到可点击的话题行: {keyword}")
            return False

        logger.info(f"进入话题: {(row.get('label') or '')[:80]}")
        self.client.device.press(row.get("ref"))
        time.sleep(3)

        def _topic_detail_ready(ns: List[Dict]) -> bool:
            text = " ".join(n.get("label", "") for n in ns)
            if "次播放" in text or "亿次播放" in text or "万次播放" in text:
                return True
            if keyword in text and ("讨论" in text or "作品" in text or "视频" in text):
                return True
            if any(n.get("label", "").strip() == "视频" and n.get("hittable") for n in ns):
                return True
            return False

        try:
            self.client.wait_for_page(_topic_detail_ready, timeout=12, desc="话题详情页")
        except TimeoutError:
            logger.warning("话题详情页特征未完全匹配，仍尝试列表采集")
        return True

    def _find_topic_tab(self, nodes: List[Dict]) -> Optional[Dict]:
        for n in nodes:
            lab = n.get("label", "").strip()
            if n.get("hittable") and lab == "话题":
                return n
        for n in nodes:
            lab = n.get("label", "").strip()
            if n.get("hittable") and lab.startswith("话题") and len(lab) <= 4:
                return n
        return None

    def _pick_topic_row(
        self, nodes: List[Dict], keyword: str, *, strict_play_count: bool
    ) -> Optional[Dict]:
        """
        优先匹配 #关键词、带播放量的话题行。
        strict_play_count：未点到「话题」Tab 时要求行内含播放量/讨论，避免误点搜索联想。
        """

        def score(n: Dict) -> int:
            if not n.get("hittable"):
                return -1
            lab = n.get("label", "").strip()
            if keyword not in lab and f"#{keyword}" not in lab:
                return -1
            if strict_play_count and not any(
                x in lab for x in ("次播放", "亿次播放", "万次播放", "讨论")
            ):
                return -1
            s = 0
            if lab == f"#{keyword}" or lab.startswith(f"#{keyword}"):
                s += 80
            if lab == keyword:
                s += 70
            if "次播放" in lab or "播放" in lab:
                s += 40
            if len(lab) < 80:
                s += 5
            return s

        ranked = [(score(n), n) for n in nodes]
        ranked = [(s, n) for s, n in ranked if s >= 0]
        if not ranked:
            return None
        ranked.sort(key=lambda x: x[0], reverse=True)
        return ranked[0][1]

    # ------------------------------------------------------------------
    # 采集
    # ------------------------------------------------------------------

    def _collect(self, count: int) -> List[Dict[str, Any]]:
        """滚动采集：仅将「成功进入全屏视频并完成解析」的条目计入 count，避免商品卡/失败点击占名额。"""
        results: List[Dict[str, Any]] = []
        seen_titles: set = set()
        scroll_count = 0
        stagnant = 0
        max_scrolls = max(count * 5, 40)

        logger.info("滚动到搜索结果列表")
        self.client.adb.swipe(540, 1500, 540, 500, duration=500)
        time.sleep(2)

        while len(results) < count and scroll_count < max_scrolls:
            nodes = self.client.get_nodes()
            new_items = self._parse_results(nodes)
            n_before = len(results)

            for item in new_items:
                t = item.get("title", "").strip()
                if not t or t in seen_titles:
                    continue
                seen_titles.add(t)
                detailed_item, ok = self._enter_and_collect(item, nodes)
                detailed_item["search_keyword"] = self._keyword
                if self._topic_mode:
                    detailed_item["topic"] = self._keyword
                    detailed_item["type"] = "话题视频"
                if ok:
                    results.append(detailed_item)
                    logger.info(
                        f"[{len(results)}/{count}] {detailed_item.get('nickname') or '?'}: {t[:40]}"
                    )
                else:
                    logger.warning(f"未进全屏，跳过不计入: {t[:40]}")
                if len(results) >= count:
                    break

            if len(results) < count:
                self.client.adb.swipe(540, 1600, 540, 600, duration=400)
                time.sleep(1.8)
                scroll_count += 1
                if len(results) == n_before:
                    stagnant += 1
                    if stagnant >= 14:
                        logger.warning(f"连续 {stagnant} 次滑动无新有效作品，停止（已 {len(results)}/{count} 条）")
                        break
                else:
                    stagnant = 0

        logger.success(f"搜索采集完成: {len(results)} 条（目标 {count}）")
        return results

    @staticmethod
    def _looks_like_immersive_video(nodes: List[Dict]) -> bool:
        """与推荐流一致：未/已点赞、或带数字的评论按钮"""
        for n in nodes:
            lab = n.get("label", "").strip()
            if re.match(r"^(未|已)点赞，喜欢", lab):
                return True
            if n.get("hittable") and lab.startswith("评论") and re.search(r"\d+", lab):
                return True
        return False

    def _open_video_from_list(self, item: Dict[str, Any], nodes: List[Dict]) -> List[Dict]:
        """从话题/搜索列表进入全屏播放页；ref 点击失败时用列表区域坐标兜底"""
        title = item.get("title", "")
        candidates = [n for n in nodes if n.get("label", "").strip() == title]
        tap = next((n for n in candidates if n.get("hittable")), None)
        if not tap and candidates:
            tap = candidates[0]
        if tap and tap.get("ref"):
            logger.info(f"点击列表项: {title[:40]!r}")
            data = self.client.device.press(tap["ref"])
            time.sleep(3.2 if data else 1.0)
            if not data:
                logger.warning("ref 点击失败，尝试列表区坐标")
                for y in (1120, 1020, 1220):
                    self.client.adb.tap(540, y)
                    time.sleep(2.8)
                    cur = self.client.get_nodes()
                    if self._looks_like_immersive_video(cur):
                        return cur
        else:
            logger.info("未匹配标题 ref，点击列表中部")
            self.client.adb.tap(540, 1050)
            time.sleep(3.5)

        cur = self.client.get_nodes()
        if self._looks_like_immersive_video(cur):
            return cur
        for _ in range(3):
            self.client.adb.tap(540, 1150)
            time.sleep(2.2)
            cur = self.client.get_nodes()
            if self._looks_like_immersive_video(cur):
                return cur
        return cur

    def _enter_and_collect(self, item: Dict[str, Any], nodes: List[Dict]) -> Tuple[Dict[str, Any], bool]:
        """进入全屏视频并采集；返回 (item, 是否成功进入全屏并完成主流程)。"""
        logger.info(f"进入作品: {(item.get('nickname') or '?')!r} — {item.get('title', '')[:36]!r}")
        item.setdefault("url", "")

        cur = self._open_video_from_list(item, nodes)
        feed = FeedFeature(self.client)

        if not self._looks_like_immersive_video(cur):
            logger.warning("未识别为全屏视频页，保留列表字段并返回")
            item["comments"] = []
            self.client.adb.press_key("KEYCODE_BACK")
            time.sleep(1.5)
            return item, False

        meta = feed._parse_video(cur)
        if meta.get("title"):
            item["title"] = meta["title"]
        if meta.get("likes"):
            item["likes"] = meta["likes"]
        if meta.get("comment_count"):
            item["comment_count"] = meta["comment_count"]
        if meta.get("nickname"):
            item["nickname"] = meta["nickname"]
        for k in ("author_handle", "shares", "music"):
            if meta.get(k):
                item[k] = meta[k]

        comments, panel_total = feed._fetch_comments(cur, max_comments=self._max_comments)
        item["comments"] = comments
        if panel_total:
            item["comment_count"] = panel_total
        logger.info(
            f"本作品评论: 解析 {len(item['comments'])}/{self._max_comments} 条，"
            f"界面总数 comment_count={item.get('comment_count', '')!r}"
        )

        for _ in range(2):
            self.client.adb.press_key("KEYCODE_BACK")
            time.sleep(1.2)
        return item, True

    def _title_matches_keyword(self, label: str) -> bool:
        """普通搜索：标题里应出现关键词；话题详情页：列表已按话题过滤，不再强制包含关键词。"""
        if self._topic_mode:
            return True
        return self._keyword in label

    def _parse_results(self, nodes: List[Dict]) -> List[Dict[str, Any]]:
        """从搜索结果页 / 话题作品列表节点解析视频卡片"""
        items = []
        i = 0
        while i < len(nodes):
            node = nodes[i]
            label = node.get("label", "").strip()

            min_title_len = 6 if self._topic_mode else 8
            _tab_exact = {
                "综合", "视频", "用户", "直播", "话题", "商品", "图文",
                "搜索", "返回", "清空", "筛选", "切换", "追问", "最热", "最新",
            }
            is_chrome = label in _tab_exact or "按钮" in label
            is_chrome = is_chrome or any(
                x in label for x in ("是否允许", "填入搜索框", "请检查网络连接")
            )

            # 视频标题：较长文本；话题页标题不一定含关键词
            if (len(label) >= min_title_len and not node.get("hittable")
                    and not is_chrome
                    and not re.match(r'^\d{4}\.\d{2}\.\d{2}$', label)
                    and not re.match(r'^\d+:\d+$', label)
                    and "次播放" not in label
                    and self._title_matches_keyword(label)):

                item = {
                    "nickname": "", "author_handle": "", "title": label,
                    "likes": "", "date": "", "comment_count": "", "shares": "",
                    "url": "", "comments": [],
                }

                # 优先在卡片窗口内找可点的 @作者（比「标题后第一个短文案」可靠）
                for j in range(i + 1, min(i + 22, len(nodes))):
                    nj = nodes[j]
                    lab = (nj.get("label") or "").strip()
                    if nj.get("hittable") and lab.startswith("@"):
                        item["author_handle"] = lab
                        item["nickname"] = lab.lstrip("@")
                        break

                # 往后找日期、互动、兜底作者
                for j in range(i + 1, min(i + 18, len(nodes))):
                    nj = nodes[j]
                    next_label = nj.get("label", "").strip()

                    if re.match(r'^\d{4}\.\d{2}\.\d{2}$', next_label) or re.match(r'^\d{2}\.\d{2}$', next_label):
                        item["date"] = next_label

                    elif "喜欢" in next_label:
                        m = re.search(r'喜欢(\S+?)(?:，|$)', next_label)
                        if m:
                            item["likes"] = m.group(1)

                    elif "评论" in next_label:
                        m = re.search(r'评论(\S+?)(?:，|$)', next_label)
                        if m:
                            item["comment_count"] = m.group(1)

                    elif "分享" in next_label:
                        m = re.search(r'分享(\S+?)(?:，|$)', next_label)
                        if m:
                            item["shares"] = m.group(1)

                    elif (not item["nickname"] and next_label and len(next_label) < 25
                          and not re.match(r'^\d', next_label)
                          and not _looks_like_bad_author_nickname(next_label)
                          and not any(k in next_label for k in ["按钮", "喜欢", "评论", "分享", "收藏"])):
                        item["nickname"] = next_label

                    elif len(next_label) > 8 and "按钮" not in next_label and j > i + 3:
                        break

                if item["nickname"] or item["title"]:
                    items.append(item)
                    i += 8  # 跳过已处理的节点
                    continue
            i += 1

        return items
