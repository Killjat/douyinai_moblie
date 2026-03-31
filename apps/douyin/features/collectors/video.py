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

    def __init__(self, client, max_comments: int = 100, **kwargs):
        super().__init__(client)
        self.max_comments = max(0, min(max_comments, 200))

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

        # 字幕识别（需安装 easyocr）
        item["subtitle"] = self._extract_subtitles(item["cover"])

        # 视频链接
        item["url"] = self._get_url(self.client.get_nodes())

        # 评论
        if self.max_comments > 0:
            from apps.douyin.features.feed import FeedFeature
            feed = FeedFeature(self.client)
            cur = self.client.get_nodes()
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
        """点击列表项进入全屏播放页。"""
        title = item.get("title", "")
        candidates = [n for n in nodes if n.get("label", "").strip() == title]
        tap = next((n for n in candidates if n.get("hittable")), None) or \
              (candidates[0] if candidates else None)

        if tap and tap.get("ref"):
            logger.info(f"点击列表项: {title[:40]!r}")
            data = self.client.device.press(tap["ref"])
            time.sleep(2.0 if data else 0.8)
            if not data:
                for y in (1120, 1020, 1220):
                    self.client.adb.tap(540, y)
                    time.sleep(1.5)
                    cur = self.client.get_nodes()
                    if self._is_fullscreen(cur):
                        return cur
        else:
            logger.info("未匹配标题 ref，点击列表中部")
            self.client.adb.tap(540, 1050)
            time.sleep(2.0)

        cur = self.client.get_nodes()
        if self._is_fullscreen(cur):
            return cur
        for _ in range(2):
            self.client.adb.tap(540, 1150)
            time.sleep(1.5)
            cur = self.client.get_nodes()
            if self._is_fullscreen(cur):
                return cur
        return cur

    @staticmethod
    def _is_fullscreen(nodes: List[Dict]) -> bool:
        """判断当前是否在全屏视频页。"""
        for n in nodes:
            lab = n.get("label", "").strip()
            if re.match(r"^(未|已)点赞，喜欢", lab):
                return True
            if n.get("hittable") and lab.startswith("评论") and re.search(r"\d+", lab):
                return True
        return False

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
        """用 EasyOCR 识别截图下半部分的字幕文字。"""
        if not image_path or not os.path.exists(image_path):
            return ""
        try:
            import easyocr
            from PIL import Image as PILImage
            import numpy as np
            img = PILImage.open(image_path).convert("RGB")
            w, h = img.size
            region = img.crop((0, int(h * 0.5), w, int(h * 0.85)))
            reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
            results = reader.readtext(np.array(region), detail=0)
            subtitle = " ".join(results).strip()
            logger.info(f"字幕识别: {subtitle[:60]!r}")
            return subtitle
        except ImportError:
            logger.warning("未安装 easyocr，跳过字幕识别。pip install easyocr")
            return ""
        except Exception as e:
            logger.warning(f"字幕识别失败: {e}")
            return ""

    def _get_url(self, nodes: List[Dict]) -> str:
        """点分享 → 复制链接 → 粘贴到搜索框读取 URL。"""
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
                (n for n in share_nodes if n.get("hittable")
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

            # 粘贴到搜索框读取
            search_btn = next(
                (n for n in self.client.get_nodes()
                 if n.get("hittable") and n.get("label", "").strip() == "搜索"),
                None
            )
            if not search_btn:
                return ""
            self.client.device.press(search_btn.get("ref"))
            time.sleep(1.0)
            self.client.adb.tap(540, 80)
            time.sleep(0.5)
            self.client.adb.execute(["shell", "input", "keyevent", "KEYCODE_PASTE"])
            time.sleep(0.8)

            url = ""
            for n in self.client.get_nodes():
                for field in (n.get("value", ""), n.get("label", "")):
                    if "douyin.com" in field or "v.douyin" in field:
                        url = field.strip()
                        break
                if url:
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
