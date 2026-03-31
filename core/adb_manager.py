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
        """输入文本（仅适用于 ASCII，中文请用 input_text_unicode）"""
        self.execute(["shell", "input", "text", text])
        logger.debug(f"输入文本: {text}")

    def input_text_unicode(self, text: str) -> bool:
        """
        输入任意 Unicode 文本（含中文）到 Android 设备当前焦点输入框。

        Android 的 `adb shell input text` 不支持 ASCII 以外的字符，
        所有可靠方案都需要在设备上安装一个辅助 APK：

          推荐：ADBKeyboard
            安装：adb install ADBKeyboard.apk
            下载：https://github.com/senzhk/ADBKeyBoard/releases
            安装后本方法自动检测并使用，无需额外配置。

          备选：mobile-mcp DeviceKit
            安装：adb install mobilenext-devicekit.apk
            下载：https://github.com/mobile-next/devicekit-android/releases

        未安装任何辅助 APK 时，本方法会尝试 `input text` 直传（对纯 ASCII 有效），
        中文等 Unicode 字符将无法输入。
        """
        import base64
        import time

        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")

        # ── 方案 1：ADBKeyboard（切换输入法 → 输入 → 切回）────────────────
        try:
            ime_out = subprocess.run(
                ["adb", "shell", "ime", "list", "-s"],
                capture_output=True, text=True, timeout=5
            ).stdout
            if "com.android.adbkeyboard/.AdbIME" in ime_out:
                # 记录当前输入法，输入完切回
                current_ime = subprocess.run(
                    ["adb", "shell", "settings", "get", "secure", "default_input_method"],
                    capture_output=True, text=True, timeout=5
                ).stdout.strip()

                subprocess.run(
                    ["adb", "shell", "ime", "set", "com.android.adbkeyboard/.AdbIME"],
                    capture_output=True, timeout=5
                )
                time.sleep(0.3)

                subprocess.run(
                    ["adb", "shell", "am", "broadcast",
                     "-a", "ADB_INPUT_B64", "--es", "msg", b64],
                    capture_output=True, timeout=5
                )
                time.sleep(0.4)

                logger.info(f"ADBKeyboard 输入成功: {text!r}")

                # 切回原输入法（调用方负责触发搜索）
                if current_ime and current_ime != "com.android.adbkeyboard/.AdbIME":
                    subprocess.run(
                        ["adb", "shell", "ime", "set", current_ime],
                        capture_output=True, timeout=5
                    )
                return True
        except Exception:
            pass

        # ── 方案 2：mobile-mcp DeviceKit ─────────────────────────────────
        try:
            pkg_out = subprocess.run(
                ["adb", "shell", "pm", "list", "packages", "com.mobilenext.devicekit"],
                capture_output=True, text=True, timeout=5
            ).stdout
            if "com.mobilenext.devicekit" in pkg_out:
                subprocess.run(
                    ["adb", "shell", "am", "broadcast",
                     "-a", "com.mobilenext.devicekit.SET_CLIPBOARD",
                     "--es", "text", text],
                    capture_output=True, timeout=5
                )
                time.sleep(0.3)
                self.press_key("KEYCODE_PASTE")
                time.sleep(0.5)
                logger.info(f"DeviceKit 剪贴板输入成功: {text!r}")
                return True
        except Exception:
            pass

        # ── 兜底：input text 直传（仅 ASCII 有效）────────────────────────
        logger.warning(
            f"未检测到 ADBKeyboard 或 DeviceKit，中文输入可能失败。"
            f"请安装 ADBKeyboard: https://github.com/senzhk/ADBKeyBoard/releases"
        )
        try:
            result = subprocess.run(
                ["adb", "shell", "input", "text", text],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"input text 失败: {e}")
            return False

    def get_screen_size(self) -> tuple:
        """获取设备屏幕分辨率，返回 (width, height)"""
        try:
            result = subprocess.run(
                ["adb", "shell", "wm", "size"],
                capture_output=True, text=True, timeout=5
            )
            # 解析 "Physical size: 1080x2340" 或 "Override size: 1080x2340"
            for line in result.stdout.splitlines():
                if "size:" in line.lower():
                    size_str = line.split(":")[-1].strip()
                    w, h = size_str.split("x")
                    return int(w), int(h)
        except Exception as e:
            logger.warning(f"获取屏幕尺寸失败: {e}")
        return 1080, 2340  # 默认值

    def scale_tap(self, x: int, y: int, ref_width: int = 1080, ref_height: int = 2340) -> tuple:
        """将参考分辨率下的坐标按比例换算到当前设备分辨率"""
        w, h = self.get_screen_size()
        scaled_x = int(x * w / ref_width)
        scaled_y = int(y * h / ref_height)
        logger.debug(f"坐标换算: ({x},{y}) @ {ref_width}x{ref_height} → ({scaled_x},{scaled_y}) @ {w}x{h}")
        return scaled_x, scaled_y

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
