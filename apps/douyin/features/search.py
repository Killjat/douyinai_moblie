"""
搜索功能模块
- 搜索关键词，采集相关视频列表
- 支持切换到「话题」并进入话题详情页，采集该话题下的作品
- 支持滚动翻页，持续采集
"""
import re
import os
import subprocess
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
    # 1. 检查是否有搜索相关的 Tab
    tabs = {
        "综合", "视频", "用户", "直播", "话题", "商品", "图文",
        "全部", "经验", "团购", "店铺",
    }
    for n in nodes:
        if n.get("label", "").strip() in tabs:
            return True
    
    # 2. 检查是否有搜索相关的特征（不依赖特定关键词）
    # 这里不再检查特定关键词，因为关键词是动态的
    
    # 3. 无 Tab 文案时：常见「筛选」+ 多结果列表
    joined = "".join((n.get("label") or "") for n in nodes[:250])
    if "筛选" in joined and len(joined) > 80:
        return True
    
    # 4. 检查是否有搜索结果相关的文本
    if any(keyword in joined for keyword in ["结果", "找到", "条视频", "个作品"]):
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
        latest: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        搜索关键词，采集前 count 条视频。
        latest=True：切到「视频」Tab，按最新发布 + 一天内筛选，采集最新内容。
        """
        self._keyword = keyword
        self._topic_mode = topic
        self._max_comments = max(1, min(max_comments, 200))
        try:
            self.client.ensure_open()
            try:
                feed_nodes = self.client.navigate_to_feed()
            except Exception as e:
                logger.error(f"无法导航到推荐页: {e}")
                return []
            if not self._navigate_to_search(keyword, feed_nodes):
                return []
            # 默认切到「视频」Tab，过滤掉综合结果中的用户/话题/商品卡
            self._switch_to_video_tab()
            if latest:
                if not self._apply_latest_filter():
                    logger.warning("筛选失败，继续采集未筛选的结果")
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

    # ------------------------------------------------------------------
    # 页面状态感知
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_page(nodes: List[Dict]) -> str:
        """
        感知当前页面类型，返回状态字符串：
          'search_input'   搜索输入页（有历史记录/猜你想搜）
          'search_results' 搜索结果页（有综合/视频等 Tab）
          'feed'           推荐视频流（有推荐按钮）
          'unknown'        其他
        """
        labels = {n.get("label", "").strip() for n in nodes}
        # 搜索输入页
        if labels & {"历史记录", "猜你想搜", "大家都在搜"} or \
                any("填入搜索框" in l or "搜索框" in l for l in labels):
            return "search_input"
        # 搜索结果页：有搜索 Tab 栏（综合/用户/话题等）
        # 注意："视频"、"直播"、"图文" 在推荐页也存在，不能用于判断
        if labels & {"综合", "用户", "话题", "商品"}:
            return "search_results"
        # 推荐页：底部"首页"和"推荐"按钮同时存在
        if (any(n.get("label", "").strip() == "首页" for n in nodes) and
                any("推荐" in n.get("label", "") and "按钮" in n.get("label", "") for n in nodes)):
            return "feed"
        return "unknown"

    def _wait_for_state(self, target: str, timeout: int = 20) -> List[Dict]:
        """轮询直到页面状态匹配 target，返回节点列表。
        快照失败（空 nodes）时跳过本次判断继续等待。"""
        import time as _time
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            nodes = self.client.get_nodes()
            if not nodes:
                logger.debug("快照为空，继续等待...")
                continue
            state = self._detect_page(nodes)
            if state == target:
                logger.info(f"页面状态: {target}")
                return nodes
            logger.debug(f"等待 {target}，当前: {state}")
        nodes = self.client.get_nodes()
        logger.warning(f"等待 {target} 超时，当前状态: {self._detect_page(nodes)}")
        return nodes

    # ------------------------------------------------------------------
    # 导航
    # ------------------------------------------------------------------

    def _switch_to_video_tab(self) -> bool:
        """切换到搜索结果页的「视频」Tab，返回是否成功。"""
        time.sleep(1.0)
        nodes = self.client.get_nodes()
        # Tab 栏节点 hittable 可能为 False，直接按 label 匹配即可
        video_tab = next(
            (n for n in nodes if n.get("label", "").strip() == "视频" and n.get("ref")),
            None
        )
        if not video_tab:
            logger.warning("未找到「视频」Tab，保持当前 Tab")
            return False
        self.client.device.press(video_tab.get("ref"))
        time.sleep(1.5)
        logger.info("已切换到「视频」Tab")
        return True

    def _navigate_to_search(self, keyword: str, nodes: List[Dict] = None) -> bool:
        """
        导航到搜索结果页。
        优先点击历史记录（快），没有则用 ADBKeyboard 直接输入。
        """
        if nodes is None:
            nodes = self.client.get_nodes()
        if self._detect_page(nodes) != "feed":
            logger.error(f"当前不在推荐页（{self._detect_page(nodes)}），请先回到推荐页")
            return False
        logger.info("✓ 当前在推荐页")

        # 点搜索按钮
        search_btn = next(
            (n for n in nodes if n.get("hittable") and n.get("label", "").strip() == "搜索"),
            None
        )
        if not search_btn:
            logger.error("推荐页未找到搜索按钮")
            return False

        self.client.device.press(search_btn.get("ref"))
        nodes = self._wait_for_state("search_input", timeout=20)
        if self._detect_page(nodes) != "search_input":
            logger.error("未进入搜索输入页")
            return False

        # 优先点历史记录
        nodes = self._expand_history(nodes)
        history_node = self._find_history_node(nodes, keyword)
        if history_node:
            logger.info(f"✓ 历史记录命中: {self._history_label(history_node)!r}")
            self.client.device.press(history_node.get("ref"))
            nodes = self._wait_for_state("search_results", timeout=20)
            if self._detect_page(nodes) == "search_results":
                logger.info(f"历史记录搜索成功: {keyword}")
                return True
            logger.warning("历史记录点击后未进入搜索结果页，改用输入法")

        # 用 ADBKeyboard 直接输入
        logger.info(f"使用输入法搜索: {keyword!r}")
        input_node = next(
            (n for n in nodes if n.get("hittable") and "搜索" in n.get("label", "")),
            None
        )
        if input_node:
            self.client.device.press(input_node.get("ref"))
        else:
            self.client.adb.tap(540, 80)
        time.sleep(0.5)

        for _ in range(15):
            self.client.adb.press_key("KEYCODE_DEL")
        self.client.adb.input_text_unicode(keyword)
        time.sleep(0.8)

        nodes = self.client.get_nodes()
        if not any(keyword in n.get("label", "") for n in nodes):
            logger.error(f"输入验证失败，未找到 '{keyword}'")
            return False

        # 点搜索框右边的搜索按钮（第一个 label="搜索" 的节点，在输入框右侧）
        search_btns = [n for n in nodes if n.get("label", "").strip() == "搜索" and n.get("ref")]
        if search_btns:
            self.client.device.press(search_btns[0].get("ref"))  # 第一个是顶部搜索提交按钮
            logger.info("点击搜索按钮")
        else:
            self.client.adb.press_key("KEYCODE_ENTER")
            logger.info("按回车搜索")
        nodes = self._wait_for_state("search_results", timeout=20)
        if self._detect_page(nodes) == "search_results":
            logger.info(f"输入法搜索成功: {keyword}")
            return True

        logger.error("搜索结果页加载超时")
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

    # ------------------------------------------------------------------
    # 搜索历史
    # ------------------------------------------------------------------

    _BAD_HISTORY_LABELS = frozenset({
        "搜索", "填入搜索框", "搜索框", "历史记录", "猜你想搜", "大家都在搜",
        "综合", "视频", "用户", "直播", "话题", "商品", "图文",
        "清空", "删除", "全部删除", "返回", "展开", "收起",
        "换一换", "反馈", "查看更多历史", "常搜",
        "猜你想看", "抖音热榜", "同城榜", "直播榜", "团购榜",
        "语音搜",
    })
    _BAD_HISTORY_FRAGMENTS = (
        "次播放", "喜欢", "评论", "分享", "万", "亿",
        "，搜索", "，团", "，未选中", "，已选中",
        "让互联网", "置顶",
    )

    def _expand_history(self, nodes: List[Dict]) -> List[Dict]:
        """如果历史记录处于折叠状态，点击展开按钮并刷新节点"""
        for n in nodes:
            lab = re.sub(r"[，,]按钮$", "", n.get("label", "").strip())
            if lab == "展开" and n.get("ref"):
                logger.info("历史记录已折叠，点击展开")
                self.client.device.press(n.get("ref"))
                time.sleep(1.0)
                return self.client.get_nodes()
        return nodes

    def _is_history_candidate(self, node: Dict) -> bool:
        """判断一个节点是否可能是搜索历史条目"""
        if not node.get("ref"):
            return False
        raw = node.get("label", "").strip()
        lab = re.sub(r"[，,]按钮$", "", raw).strip()
        if not lab or len(lab) > 40:
            return False
        # 含 \ufeff（截断省略号节点）跳过，保留完整文本节点
        if "\ufeff" in lab:
            return False
        # 去掉后缀后仍含逗号，说明是复合描述（如"猜你想看，未选中"），不是历史词
        if "，" in lab or "," in lab:
            return False
        # "xxx搜索" 结尾是"猜你想搜"区域的推荐词，不是历史记录
        if lab.endswith("搜索"):
            return False
        if lab in self._BAD_HISTORY_LABELS:
            return False
        if any(f in lab for f in self._BAD_HISTORY_FRAGMENTS):
            return False
        if re.match(r"^\d", lab):
            return False
        return True

    def _history_label(self, node: Dict) -> str:
        """返回历史节点清理后的 label（去掉 '，按钮' 后缀）"""
        lab = node.get("label", "").strip()
        return re.sub(r"[，,]按钮$", "", lab).strip()

    def get_search_history(self) -> List[str]:
        """
        导航到搜索输入页，读取并返回当前可见的搜索历史记录列表。
        可用于在搜索前检查历史，或直接用历史关键词发起搜索。
        """
        try:
            self.client.ensure_open()
            nodes = self.client.navigate_to_feed()
        except Exception:
            nodes = self.client.get_nodes()

        # 点击搜索按钮进入搜索输入页
        search_btn = next(
            (n for n in nodes if n.get("hittable") and "搜索" in n.get("label", "")),
            None
        )
        if search_btn:
            self.client.device.press(search_btn.get("ref"))
            time.sleep(1.0)
        else:
            self.client.adb.tap(900, 100)
            time.sleep(1.5)

        nodes = self.client.get_nodes()
        nodes = self._expand_history(nodes)
        seen, history = set(), []
        for n in nodes:
            if self._is_history_candidate(n):
                lab = self._history_label(n)
                if lab not in seen:
                    seen.add(lab)
                    history.append(lab)
        logger.info(f"读取到 {len(history)} 条搜索历史: {history}")

        # 返回推荐页
        self.client.adb.press_key("KEYCODE_BACK")
        return history

    def _find_history_node(self, nodes: List[Dict], keyword: str) -> Optional[Dict]:
        """
        在搜索输入页节点中查找与 keyword 匹配的历史记录节点。
        匹配规则（优先级从高到低）：
          1. 精确匹配
          2. 去掉 # 前缀后精确匹配
          3. 节点 label 包含 keyword
        """
        exact, hash_match, contains = None, None, None
        for n in nodes:
            if not self._is_history_candidate(n):
                continue
            lab = self._history_label(n)
            if lab == keyword:
                exact = n
                break
            if lab.lstrip("#") == keyword and hash_match is None:
                hash_match = n
            if keyword in lab and contains is None:
                contains = n

        result = exact or hash_match or contains
        if result:
            logger.info(f"找到历史记录节点: {result.get('label', '')!r}")
        return result

    def _apply_latest_filter(self) -> bool:
        """切到视频 Tab → 打开筛选面板 → 点最新发布 → 关闭面板"""
        nodes = self.client.get_nodes()
        if self._detect_page(nodes) != "search_results":
            logger.error(f"不在搜索结果页: {self._detect_page(nodes)}")
            return False

        video_tab = next((n for n in nodes if n.get("label", "").strip() == "视频"), None)
        if not video_tab:
            logger.error("未找到视频 Tab")
            return False
        self.client.device.press(video_tab.get("ref"))
        time.sleep(1.5)

        nodes = self.client.get_nodes()
        if self._detect_page(nodes) != "search_results":
            logger.error(f"切视频 Tab 后状态异常: {self._detect_page(nodes)}")
            return False

        # 筛选按钮弹出的是系统弹层，accessibility tree 抓不到节点
        # 全程用 scale_tap 按比例换算坐标（参考分辨率 1080x2340）
        logger.info("点击筛选按钮")
        fx, fy = self.client.adb.scale_tap(1018, 312)  # 筛选按钮中心
        self.client.adb.tap(fx, fy)
        time.sleep(1.5)

        logger.info("点击「最新发布」")
        lx, ly = self.client.adb.scale_tap(451, 583)   # 最新发布选项
        self.client.adb.tap(lx, ly)
        time.sleep(0.5)

        logger.info("点击「完成」关闭筛选面板")
        dx, dy = self.client.adb.scale_tap(810, 583)   # 完成按钮
        self.client.adb.tap(dx, dy)
        time.sleep(2.0)

        nodes = self._wait_for_state("search_results", timeout=10)
        if self._detect_page(nodes) == "search_results":
            logger.info("筛选完成：最新发布")
            return True

        logger.error(f"筛选后状态异常: {self._detect_page(nodes)}")
        return False

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
        # 确认当前在搜索结果页，不在则尝试 back 回来
        nodes = self.client.get_nodes()
        if self._detect_page(nodes) != "search_results":
            logger.warning(f"_collect 开始时不在搜索结果页（{self._detect_page(nodes)}），尝试 back")
            self.client.adb.press_key("KEYCODE_BACK")
            time.sleep(1.5)
            nodes = self.client.get_nodes()
            if self._detect_page(nodes) != "search_results":
                logger.error("back 后仍不在搜索结果页，放弃采集")
                return results
        try:
            self.client.adb.swipe(540, 1500, 540, 500, duration=500)
            time.sleep(2)
        except Exception as e:
            logger.warning(f"滚动失败: {e}")
            # 尝试使用其他方式滚动
            try:
                self.client.adb.execute(["shell", "input", "keyevent", "KEYCODE_PAGE_DOWN"])
                time.sleep(2)
                logger.info("使用 PAGE_DOWN 键滚动")
            except Exception as e2:
                logger.warning(f"PAGE_DOWN 键滚动失败: {e2}")
                # 不滚动，直接尝试解析当前页面
                logger.info("不滚动，直接尝试解析当前页面")

        while len(results) < count and scroll_count < max_scrolls:
            nodes = self.client.get_nodes()
            new_items = self._parse_results(nodes)
            n_before = len(results)

            # 每次只取第一条未处理的视频，处理完 back 回来重新取快照
            processed_this_round = False
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
                processed_this_round = True
                break  # 处理完一条立即 break，重新取快照获取最新 ref

            if len(results) >= count:
                break

            if not processed_this_round:
                # 当前页所有条目都处理过了，滚动加载新内容
                self.client.adb.swipe(540, 1600, 540, 600, duration=400)
                time.sleep(1.8)
                scroll_count += 1
                stagnant += 1
                if stagnant >= 8:
                    logger.warning(f"连续 {stagnant} 次无新作品，停止")
                    break
            else:
                stagnant = 0

            if len(results) < count:
                if not processed_this_round:
                    # 当前页所有条目都处理过了，滚动加载新内容
                    self.client.adb.swipe(540, 1600, 540, 600, duration=400)
                    time.sleep(1.8)
                    scroll_count += 1
                    stagnant += 1
                    if stagnant >= 8:
                        logger.warning(f"连续 {stagnant} 次无新作品，停止")
                        break
                else:
                    stagnant = 0

        logger.success(f"搜索采集完成: {len(results)} 条（目标 {count}）")
        return results

    def _capture_frame(self, save_dir: str = "output/covers") -> str:
        """截取当前屏幕作为视频封面，返回保存路径。"""
        os.makedirs(save_dir, exist_ok=True)
        ts = int(time.time())
        local_path = os.path.join(save_dir, f"cover_{ts}.png")
        try:
            subprocess.run(["adb", "shell", "screencap", "-p", "/sdcard/_cover.png"],
                           capture_output=True, timeout=5)
            subprocess.run(["adb", "pull", "/sdcard/_cover.png", local_path],
                           capture_output=True, timeout=5)
            logger.info(f"封面截图: {local_path}")
        except Exception as e:
            logger.warning(f"截图失败: {e}")
            return ""
        return local_path

    def _extract_subtitles(self, image_path: str) -> str:
        """用 EasyOCR 识别视频截图中的字幕文字（截图下半部分字幕区域）。"""
        if not image_path or not os.path.exists(image_path):
            return ""
        try:
            import easyocr
            from PIL import Image as PILImage
            import numpy as np

            # 只裁取下半部分（字幕通常在 50%~85% 高度区间）
            img = PILImage.open(image_path).convert("RGB")
            w, h = img.size
            subtitle_region = img.crop((0, int(h * 0.5), w, int(h * 0.85)))

            reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
            results = reader.readtext(np.array(subtitle_region), detail=0)
            subtitle = " ".join(results).strip()
            logger.info(f"字幕识别(OCR): {subtitle[:60]!r}")
            return subtitle
        except ImportError:
            logger.warning("未安装 easyocr，跳过字幕识别。可运行: pip install easyocr")
            return ""
        except Exception as e:
            logger.warning(f"字幕识别失败: {e}")
            return ""

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
            time.sleep(2.0 if data else 0.8)
            if not data:
                logger.warning("ref 点击失败，尝试列表区坐标")
                for y in (1120, 1020, 1220):
                    self.client.adb.tap(540, y)
                    time.sleep(1.5)
                    cur = self.client.get_nodes()
                    if self._looks_like_immersive_video(cur):
                        return cur
        else:
            logger.info("未匹配标题 ref，点击列表中部")
            self.client.adb.tap(540, 1050)
            time.sleep(2.0)

        cur = self.client.get_nodes()
        if self._looks_like_immersive_video(cur):
            return cur
        for _ in range(2):  # 减少尝试次数
            self.client.adb.tap(540, 1150)
            time.sleep(1.5)
            cur = self.client.get_nodes()
            if self._looks_like_immersive_video(cur):
                return cur
        return cur

    def _get_video_url(self, nodes: List[Dict]) -> str:
        """
        点分享 → 复制链接 → 粘贴到搜索框读取 URL。
        """
        share_btn = next(
            (n for n in nodes
             if n.get("hittable") and "分享" in n.get("label", "")
             and "按钮" in n.get("label", "")),
            None
        )
        if not share_btn:
            return ""

        try:
            self.client.device.press(share_btn.get("ref"))
            time.sleep(2.0)

            share_nodes = self.client.get_nodes()
            copy_link_btn = next(
                (n for n in share_nodes
                 if n.get("hittable") and
                 any(k in n.get("label", "") for k in ["复制链接", "分享链接"])),
                None
            )
            if not copy_link_btn:
                self.client.adb.press_key("KEYCODE_BACK")
                time.sleep(0.8)
                return ""

            self.client.device.press(copy_link_btn.get("ref"))
            time.sleep(0.8)
            # 关闭分享面板
            self.client.adb.press_key("KEYCODE_BACK")
            time.sleep(0.8)

            # 点搜索框，粘贴，读取节点里的文本
            search_btn = next(
                (n for n in self.client.get_nodes()
                 if n.get("hittable") and n.get("label", "").strip() == "搜索"),
                None
            )
            if not search_btn:
                return ""
            self.client.device.press(search_btn.get("ref"))
            time.sleep(1.0)

            # 长按输入框触发粘贴
            self.client.adb.tap(540, 80)
            time.sleep(0.5)
            self.client.adb.execute(["shell", "input", "keyevent", "KEYCODE_PASTE"])
            time.sleep(0.8)

            # 从节点读取粘贴进去的文本
            input_nodes = self.client.get_nodes()
            url = ""
            for n in input_nodes:
                val = n.get("value", "").strip()
                if "douyin.com" in val or "v.douyin" in val:
                    url = val
                    break
                lab = n.get("label", "").strip()
                if "douyin.com" in lab or "v.douyin" in lab:
                    url = lab
                    break

            # 退出搜索框
            self.client.adb.press_key("KEYCODE_BACK")
            time.sleep(0.5)

            if url:
                logger.info(f"获取到视频链接: {url}")
            return url

        except Exception as e:
            logger.debug(f"获取链接失败: {e}")
            try:
                self.client.adb.press_key("KEYCODE_BACK")
            except Exception:
                pass
            return ""

    def _enter_and_collect(self, item: Dict[str, Any], nodes: List[Dict]) -> Tuple[Dict[str, Any], bool]:
        """进入全屏视频并采集；返回 (item, 是否成功进入全屏并完成主流程)。"""
        logger.info(f"进入作品: {(item.get('nickname') or '?')!r} — {item.get('title', '')[:36]!r}")

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

        # 截封面 + 识别字幕 + 获取视频链接
        cover_path = self._capture_frame()
        item["cover"] = cover_path
        item["subtitle"] = self._extract_subtitles(cover_path)
        item["url"] = self._get_video_url(self.client.get_nodes())

        # 重新获取最新节点再采评论（避免旧 nodes 的 ref 失效）
        cur = self.client.get_nodes()
        comments, panel_total = feed._fetch_comments(cur, max_comments=self._max_comments)
        item["comments"] = comments
        if panel_total:
            item["comment_count"] = panel_total
        logger.info(
            f"本作品评论: 解析 {len(item['comments'])}/{self._max_comments} 条，"
            f"界面总数 comment_count={item.get('comment_count', '')!r}"
        )

        self.client.adb.press_key("KEYCODE_BACK")
        time.sleep(1.5)
        # 确保回到搜索结果列表（不是搜索输入页）
        nodes = self.client.get_nodes()
        if self._detect_page(nodes) != "search_results":
            logger.warning(f"back 后不在搜索结果页，当前: {self._detect_page(nodes)}")
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

            min_title_len = 5  # 降低标题长度要求，确保能识别更多作品
            _tab_exact = {
                "综合", "视频", "用户", "直播", "话题", "商品", "图文",
                "搜索", "返回", "清空", "筛选", "切换", "追问", "最热", "最新",
            }
            is_chrome = label in _tab_exact or "按钮" in label
            is_chrome = is_chrome or any(
                x in label for x in ("是否允许", "填入搜索框", "请检查网络连接",
                                     "大家都在搜", "猜你想搜", "相关搜索", "章节要点",
                                     "· 20")  # 章节时间戳格式
            )
            # 直播间卡片不是视频，跳过
            is_live = "点击进入直播间" in label or label == "直播中"
            # 时间戳不是标题
            is_timestamp = bool(
                re.match(r'^(昨天|今天|前天)\d{1,2}:\d{2}$', label) or
                re.match(r'^\d{1,2}:\d{2}$', label) or
                re.match(r'^\d+[天小时分钟秒]前$', label)
            )

            # 视频标题：较长文本；不再强制要求包含关键词，以提高识别率
            if (len(label) >= min_title_len and not node.get("hittable")
                    and not is_chrome
                    and not is_live
                    and not is_timestamp
                    and not re.match(r'^\d{4}\.\d{2}\.\d{2}$', label)
                    and not re.match(r'^\d+:\d+$', label)
                    and "次播放" not in label):

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
                for j in range(i + 1, min(i + 25, len(nodes))):  # 增加搜索范围
                    nj = nodes[j]
                    next_label = nj.get("label", "").strip()

                    if re.match(r'^\d{4}\.\d{2}\.\d{2}$', next_label) or re.match(r'^\d{2}\.\d{2}$', next_label):
                        item["date"] = next_label
                    elif re.search(r'^\d+[天小时分钟秒]前$', next_label) or next_label in ("昨天", "前天"):
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

                    elif (not item["nickname"] and next_label and len(next_label) < 30  # 增加长度限制
                          and not re.match(r'^\d', next_label)
                          and not _looks_like_bad_author_nickname(next_label)
                          and not any(k in next_label for k in ["按钮", "喜欢", "评论", "分享", "收藏"])):
                        item["nickname"] = next_label

                    # 遇到下一个视频标题就停止
                    elif (len(next_label) >= min_title_len and not nj.get("hittable")
                          and not is_chrome
                          and not re.match(r'^\d{4}\.\d{2}\.\d{2}$', next_label)
                          and not re.match(r'^\d+:\d+$', next_label)
                          and "次播放" not in next_label):
                        break

                # 即使没有作者，也添加作品
                if item["title"]:
                    items.append(item)
                    i += 10  # 跳过已处理的节点
                    continue
            i += 1

        logger.info(f"解析到 {len(items)} 个作品")
        return items
