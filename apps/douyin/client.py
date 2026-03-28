"""
抖音客户端 - 只负责基础设施：设备连接、页面等待、导航、状态恢复
业务功能请使用 apps/douyin/features/ 下的各模块
"""
import time
import subprocess
from typing import Dict, List, Callable, Optional
from loguru import logger
from core.device_controller import DeviceController
from core.adb_manager import ADBManager

# 页面特征签名：通过快照节点标签识别当前页面
PAGE_SIGNATURES = {
    "douyin_any":      lambda nodes: any("com.ss.android.ugc.aweme" in n.get("identifier", "") for n in nodes),
    "douyin_feed":     lambda nodes: any("推荐" in n.get("label", "") and "按钮" in n.get("label", "") for n in nodes),
    "douyin_profile":  lambda nodes: any(n.get("label", "").strip() == "编辑主页" for n in nodes),
    "douyin_comments": lambda nodes: any("条评论" in n.get("label", "") or n.get("label", "").strip() == "关闭" for n in nodes),
}


class DouyinClient:
    """
    抖音基础客户端

    职责：
    - 设备连接与抖音启动
    - 页面状态检测与等待
    - 页面间导航
    - 操作完成后回到推荐页（统一的干净状态）

    不包含任何业务逻辑，业务逻辑由 features/ 下各模块实现。
    """

    def __init__(self, device_id: Optional[str] = None):
        self.device = DeviceController(device_id)
        self.adb = ADBManager()

    # ------------------------------------------------------------------
    # 基础工具
    # ------------------------------------------------------------------

    def get_nodes(self) -> List[Dict]:
        """获取当前页面所有节点"""
        return self.device.get_snapshot().get("nodes", [])

    def wait_for_page(
        self,
        page_check: Callable[[List], bool],
        timeout: int = 10,
        desc: str = "",
        poll_interval: float = 1.0,
    ) -> List[Dict]:
        """轮询快照直到页面特征匹配，超时抛 TimeoutError。poll_interval 过小会增加 snapshot 频率。"""
        deadline = time.time() + timeout
        poll_interval = max(0.25, float(poll_interval))
        while time.time() < deadline:
            nodes = self.get_nodes()
            if page_check(nodes):
                logger.info(f"页面就绪: {desc}")
                return nodes
            time.sleep(poll_interval)
        raise TimeoutError(f"等待页面超时: {desc}")

    # ------------------------------------------------------------------
    # 启动 / 导航
    # ------------------------------------------------------------------

    def ensure_open(self) -> None:
        """确保抖音已在前台，否则启动并等待加载"""
        if PAGE_SIGNATURES["douyin_any"](self.get_nodes()):
            logger.info("抖音已在前台")
            return
        logger.info("启动抖音...")
        subprocess.run(
            ["agent-device", "open", "com.ss.android.ugc.aweme", "--json"],
            capture_output=True, text=True, timeout=15
        )
        self.wait_for_page(PAGE_SIGNATURES["douyin_any"], timeout=15, desc="抖音启动")

    def navigate_to_feed(self) -> List[Dict]:
        """导航到推荐视频流，返回该页面 nodes"""
        nodes = self.get_nodes()
        if PAGE_SIGNATURES["douyin_feed"](nodes):
            logger.info("已在推荐页")
            return nodes

        # 个人主页需要先 back
        if PAGE_SIGNATURES["douyin_profile"](nodes):
            self.adb.press_key("KEYCODE_BACK")
            time.sleep(1)
            nodes = self.get_nodes()

        home_node = next(
            (n for n in nodes if n.get("label", "").strip() == "首页" and n.get("hittable", False)),
            None
        )
        if home_node:
            self.device.press(home_node.get("ref"))

        return self.wait_for_page(PAGE_SIGNATURES["douyin_feed"], timeout=10, desc="推荐视频流")

    def navigate_to_profile(self) -> List[Dict]:
        """导航到个人主页，返回该页面 nodes"""
        nodes = self.get_nodes()
        if PAGE_SIGNATURES["douyin_profile"](nodes):
            logger.info("已在个人主页")
            return nodes

        me_node = next((n for n in nodes if n.get("label", "").strip() == "我"), None)
        if not me_node:
            raise RuntimeError("未找到底部导航'我'按钮")

        self.device.press(me_node.get("ref"))
        return self.wait_for_page(PAGE_SIGNATURES["douyin_profile"], timeout=10, desc="个人主页")

    def return_to_feed(self) -> None:
        """操作完成后回到推荐页（统一的干净状态），最多 back 5 次"""
        for _ in range(5):
            if PAGE_SIGNATURES["douyin_feed"](self.get_nodes()):
                logger.info("已回到推荐页")
                return
            self.adb.press_key("KEYCODE_BACK")
            time.sleep(1)
        logger.warning("未能通过 back 回到推荐页")
