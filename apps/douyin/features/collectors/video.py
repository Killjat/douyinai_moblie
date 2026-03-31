"""
视频采集器 - 进入全屏视频，采集元数据、封面、字幕、链接、评论。
"""
import os
import re
import subprocess
import time
from typing import Dict, List, Tuple, Any

from loguru import logger
from apps.douyin.features.collectors.base import BaseCollector


class VideoCollector(BaseCollector):

    content_type = "video"

    def __init__(self, client, max_comments: int = 100, fetch_url: bool = False, **kwargs):
        super().__init__(client)
        self.max_comments = max(0, min(max_comments, 200))
        self.fetch_url = fetch_url  # 默认关闭，开启会增加每条视频约5秒耗时

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def collect(self, item: Dict[str, Any], nodes: List[Dict]) -> Tuple[Dict[str, Any], bool]:
        """进入全屏视频，采集完整数据，返回 (item, 是否成功)。"""
        logger.info(f"进入作品: {(item.get('nickname') or '?')!r} — {item.get('title', '')[:36]!r}")

        cur = self._open_video(item, nodes)

        if not self._is_fullscreen(cur):
            logger.warning("未识别为全屏视频页，保留列表字段并返回")
            item["comments"] = []
            self.client.adb.press_key("KEYCODE_BACK")
            time.sleep(1.5)
            return item, False

        # 解析全屏元数据
        self._enrich_meta(item, cur)

        # 封面截图
        item["cover"] = self._capture_frame()

        # 字幕识别（暂不支持）
        item["subtitle"] = self._extract_subtitles(item["cover"])

        # 视频链接（可选，默认关闭）
        item["url"] = self._get_url(self.client.get_nodes()) if self.fetch_url else ""

        # 等待页面完全加载（评论按钮 + 点赞按钮都出现）再采评论
        if self.max_comments > 0:
            from apps.douyin.features.feed import FeedFeature
            feed = FeedFeature(self.client)
            try:
                cur = self.client.wait_for_page(
                    self._is_fullscreen_ready, timeout=15, desc="全屏视频加载完成"
                )
            except TimeoutError:
                logger.warning("等待全屏加载超时，尝试直接采集评论")
                cur = self.client.get_nodes()

            if not self._is_fullscreen(cur):
                logger.warning("采集评论前页面已离开全屏，跳过评论")
                item["comments"] = []
            else:
                comments, panel_total = feed._fetch_comments(cur, max_comments=self.max_comments)
                item["comments"] = comments
                if panel_total:
                    item["comment_count"] = panel_total
                logger.info(
                    f"评论: {len(item['comments'])}/{self.max_comments} 条，"
                    f"总数={item.get('comment_count', '')!r}"
                )
        else:
            item["comments"] = []

        self.client.adb.press_key("KEYCODE_BACK")
        time.sleep(1.5)
        return item, True

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _open_video(self, item: Dict[str, Any], nodes: List[Dict]) -> List[Dict]:
        """点击列表项进入全屏播放页，轮询等待页面加载完成。"""
        title = item.get("title", "")
        candidates = [n for n in nodes if n.get("label", "").strip() == title]
        tap = next((n for n in candidates if n.get("hittable")), None) or \
              (candidates[0] if candidates else None)

        if tap and tap.get("ref"):
            logger.info(f"点击列表项: {title[:40]!r}")
            self.client.device.press(tap["ref"])
        else:
            logger.info("未匹配标题 ref，点击列表中部")
            self.client.adb.tap(540, 1050)

        # 轮询等待全屏页面出现（最多15秒）
        try:
            return self.client.wait_for_page(
                self._is_fullscreen, timeout=15, desc="全屏视频页"
            )
        except TimeoutError:
            # 兜底：尝试点击屏幕中部
            for y in (1120, 1020, 1220):
                self.client.adb.tap(540, y)
                try:
                    return self.client.wait_for_page(
                        self._is_fullscreen, timeout=5, desc="全屏视频页（兜底）"
                    )
                except TimeoutError:
                    continue
            return self.client.get_nodes()

    @staticmethod
    def _is_fullscreen(nodes: List[Dict]) -> bool:
        """判断当前是否在全屏视频页（基础判断）。"""
        for n in nodes:
            lab = n.get("label", "").strip()
            if re.match(r"^(未|已)点赞，喜欢", lab):
                return True
            if n.get("hittable") and lab.startswith("评论") and re.search(r"\d+", lab):
                return True
        return False

    @staticmethod
    def _is_fullscreen_ready(nodes: List[Dict]) -> bool:
        """判断全屏视频页是否完全加载（评论按钮 + 点赞按钮都已渲染）。"""
        has_comment = any(
            n.get("hittable") and n.get("label", "").startswith("评论")
            and re.search(r"\d+", n.get("label", ""))
            for n in nodes
        )
        has_like = any(
            re.match(r"^(未|已)点赞，喜欢", n.get("label", "").strip())
            for n in nodes
        )
        return has_comment and has_like

    def _enrich_meta(self, item: Dict[str, Any], nodes: List[Dict]) -> None:
        """从全屏节点补充元数据字段。"""
        from apps.douyin.features.feed import FeedFeature
        meta = FeedFeature(self.client)._parse_video(nodes)
        for k in ("title", "likes", "comment_count", "nickname", "author_handle", "shares", "music"):
            if meta.get(k):
                item[k] = meta[k]

    def _capture_frame(self, save_dir: str = "output/covers") -> str:
        """截取当前屏幕作为封面，返回本地路径。"""
        os.makedirs(save_dir, exist_ok=True)
        local_path = os.path.join(save_dir, f"cover_{int(time.time())}.png")
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
        """字幕识别（暂不支持，留空）"""
        return ""

    def _get_url(self, nodes: List[Dict]) -> str:
        """点分享 → 复制链接 → 粘贴到搜索框 EditText → 从 value 提取 URL。"""
        share_btn = next(
            (n for n in nodes if n.get("hittable")
             and "分享" in n.get("label", "") and "按钮" in n.get("label", "")),
            None
        )
        if not share_btn:
            return ""
        try:
            self.client.device.press(share_btn.get("ref"))
            time.sleep(2.0)
            share_nodes = self.client.get_nodes()
            copy_btn = next(
                (n for n in share_nodes if n.get("ref")
                 and any(k in n.get("label", "") for k in ["复制链接", "分享链接"])),
                None
            )
            if not copy_btn:
                self.client.adb.press_key("KEYCODE_BACK")
                time.sleep(0.8)
                return ""
            self.client.device.press(copy_btn.get("ref"))
            time.sleep(0.8)
            self.client.adb.press_key("KEYCODE_BACK")
            time.sleep(0.8)

            # 打开搜索框，粘贴，从 EditText.value 提取 URL
            cur_nodes = self.client.get_nodes()
            logger.debug(f"关闭分享面板后节点labels: {[n.get('label','').strip() for n in cur_nodes if n.get('label','').strip()][:10]}")
            search_btn = next(
                (n for n in cur_nodes
                 if n.get("hittable") and n.get("label", "").strip() == "搜索"),
                None
            )
            if not search_btn:
                logger.warning("关闭分享面板后未找到搜索按钮，跳过 URL 获取")
                return ""
            self.client.device.press(search_btn.get("ref"))
            time.sleep(1.0)
            self.client.adb.tap(540, 80)
            time.sleep(0.3)
            self.client.adb.execute(["shell", "input", "keyevent", "KEYCODE_PASTE"])
            time.sleep(1.0)

            # 从 EditText 的 value 里用正则提取 URL
            url = ""
            for n in self.client.get_nodes():
                if n.get("type", "") == "android.widget.EditText":
                    text = n.get("value", "") or n.get("label", "")
                    match = re.search(r"https?://\S+", text)
                    if match:
                        url = match.group(0).rstrip("。，、…")
                        break

            self.client.adb.press_key("KEYCODE_BACK")
            time.sleep(0.5)
            if url:
                logger.info(f"视频链接: {url}")
            return url
        except Exception as e:
            logger.debug(f"获取链接失败: {e}")
            try:
                self.client.adb.press_key("KEYCODE_BACK")
            except Exception:
                pass
            return ""
