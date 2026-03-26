"""
ADB 设备管理模块
"""
import subprocess
from typing import List, Optional
from loguru import logger


class ADBManager:
    """ADB 设备管理器"""

    def __init__(self):
        """初始化 ADB 管理器"""
        self._check_adb_installed()

    def _check_adb_installed(self) -> None:
        """检查 ADB 是否已安装"""
        try:
            result = subprocess.run(
                ["adb", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            logger.info(f"ADB 版本: {result.stdout.split()[4]}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.error("ADB 未安装或不在 PATH 中")
            raise RuntimeError("ADB 未安装，请先安装 Android Platform Tools")

    def get_devices(self) -> List[str]:
        """获取已连接的设备列表"""
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=5
            )
            lines = result.stdout.strip().split('\n')[1:]
            devices = []
            for line in lines:
                if line.strip():
                    device_id = line.split('\t')[0]
                    if device_id != "List of devices attached":
                        devices.append(device_id)
            return devices
        except subprocess.TimeoutExpired:
            logger.error("获取设备列表超时")
            return []

    def is_device_connected(self) -> bool:
        """检查是否有设备连接"""
        return len(self.get_devices()) > 0

    def execute(self, command: List[str]) -> str:
        """执行 ADB 命令"""
        try:
            result = subprocess.run(
                ["adb"] + command,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                logger.error(f"ADB 命令执行失败: {result.stderr}")
                raise RuntimeError(f"ADB 命令执行失败: {result.stderr}")
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.error("ADB 命令执行超时")
            raise RuntimeError("ADB 命令执行超时")

    def tap(self, x: int, y: int) -> None:
        """点击屏幕坐标"""
        self.execute(["shell", "input", "tap", str(x), str(y)])
        logger.debug(f"点击坐标: ({x}, {y})")

    def input_text(self, text: str) -> None:
        """输入文本"""
        self.execute(["shell", "input", "text", text])
        logger.debug(f"输入文本: {text}")

    def press_key(self, keycode: str) -> None:
        """按键事件"""
        self.execute(["shell", "input", "keyevent", keycode])
        logger.debug(f"按键: {keycode}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> None:
        """滑动屏幕"""
        self.execute(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])
        logger.debug(f"滑动: ({x1}, {y1}) -> ({x2}, {y2})")

    def wake_up_device(self) -> None:
        """唤醒设备"""
        self.press_key("KEYCODE_WAKEUP")
        logger.info("设备已唤醒")

    def unlock_device(self) -> None:
        """解锁设备 (需要设备未设置密码)"""
        self.swipe(500, 2000, 500, 1000)
        logger.info("设备已解锁")
