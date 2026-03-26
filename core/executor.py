"""
手脚执行器 - 负责 AI 决策的具体执行
"""
import subprocess
import time
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from loguru import logger

from core.device_controller import DeviceController
from core.adb_manager import ADBManager


class Executor:
    """手脚执行器 - 执行 AI 的决策"""

    def __init__(self, device_id: Optional[str] = None):
        """初始化执行器

        Args:
            device_id: 设备 ID
        """
        self.device = DeviceController(device_id)
        self.adb = ADBManager()

    def execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个步骤

        Args:
            step: 步骤信息

        Returns:
            执行结果
        """
        action = step.get("action")
        logger.info(f"执行步骤 {step.get('step')}: {step.get('description')}")
        logger.debug(f"动作类型: {action}, 参数: {step}")

        try:
            if action == "open_app":
                result = self._open_app(step["target"])
            elif action == "click_by_text":
                result = self._click_by_text(step["target"])
            elif action == "click_by_ref":
                result = self._click_by_ref(step["target"])
            elif action == "wait":
                result = self._wait(step.get("duration", 1))
            elif action == "swipe":
                result = self._swipe(step.get("x1", 500), step.get("y1", 2000), step.get("x2", 500), step.get("y2", 1000))
            elif action == "back":
                result = self._back()
            elif action == "home":
                result = self._home()
            elif action == "extract_profile_info":
                result = self._extract_profile_info()
            elif action == "screenshot":
                result = self._screenshot()
            else:
                logger.warning(f"未知的动作类型: {action}")
                result = {"success": False, "error": f"未知动作: {action}"}

            # 等待页面稳定
            if step.get("wait", 0) > 0:
                time.sleep(step["wait"])

            return {"success": True, "result": result, "action": action}

        except Exception as e:
            logger.error(f"执行步骤失败: {e}")
            return {"success": False, "error": str(e), "action": action}

    def _open_app(self, package_name: str) -> Dict[str, Any]:
        """打开应用"""
        logger.info(f"打开应用: {package_name}")
        result = subprocess.run(
            ["agent-device", "open", package_name, "--json"],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            logger.success(f"成功打开应用: {package_name}")
            return {"status": "opened"}
        else:
            logger.error(f"打开应用失败: {result.stderr}")
            raise RuntimeError(f"打开应用失败: {result.stderr}")

    def _click_by_text(self, text: str) -> Dict[str, Any]:
        """通过文本点击"""
        logger.info(f"通过文本点击: {text}")

        # 查找包含指定文本的元素
        snapshot = self.device.get_snapshot()
        nodes = snapshot.get("nodes", [])

        # 优先查找精确匹配
        exact_matches = [n for n in nodes if n.get("label", "").strip() == text]
        if exact_matches:
            ref = exact_matches[0].get("ref")
            logger.info(f"找到精确匹配: {ref}")
            return self._click_by_ref(ref)

        # 其次查找包含
        partial_matches = [n for n in nodes if text in n.get("label", "")]
        if partial_matches:
            ref = partial_matches[0].get("ref")
            logger.info(f"找到包含匹配: {ref}")
            return self._click_by_ref(ref)

        logger.warning(f"未找到包含文本 '{text}' 的元素")
        raise ValueError(f"未找到包含文本 '{text}' 的元素")

    def _click_by_ref(self, ref: str) -> Dict[str, Any]:
        """通过 ref 点击"""
        logger.info(f"通过 ref 点击: {ref}")
        result = self.device.press(f"@{ref}")
        return result or {"status": "clicked"}

    def _wait(self, duration: float) -> Dict[str, Any]:
        """等待"""
        logger.info(f"等待 {duration} 秒")
        time.sleep(duration)
        return {"status": "waited"}

    def _swipe(self, x1: int, y1: int, x2: int, y2: int) -> Dict[str, Any]:
        """滑动"""
        logger.info(f"滑动: ({x1}, {y1}) -> ({x2}, {y2})")
        self.adb.swipe(x1, y1, x2, y2)
        return {"status": "swiped"}

    def _back(self) -> Dict[str, Any]:
        """返回"""
        logger.info("返回")
        self.adb.press_key("KEYCODE_BACK")
        return {"status": "backed"}

    def _home(self) -> Dict[str, Any]:
        """返回首页"""
        logger.info("返回首页")
        self.adb.press_key("KEYCODE_HOME")
        return {"status": "homed"}

    def _extract_profile_info(self) -> Dict[str, Any]:
        """提取个人主页信息"""
        logger.info("提取个人主页信息...")

        snapshot = self.device.get_snapshot()
        nodes = snapshot.get("nodes", [])

        info = {
            "name": "",
            "bio": "",
            "followers": 0,
            "following": 0,
            "likes": 0
        }

        import re
        for node in nodes:
            label = node.get("label", "")
            if not label:
                continue

            # 查找用户名
            if "@" in label and not info["name"] and label.count("@") == 1:
                info["name"] = label
                logger.info(f"找到昵称: {label}")

            # 查找粉丝
            elif "粉丝" in label and "新关注" not in label and "关注" not in label:
                match = re.search(r'(\d+).*粉丝', label)
                if match:
                    info["followers"] = int(match.group(1))
                    logger.info(f"粉丝数: {label}")

            # 查找关注
            elif "关注" in label and "粉丝" not in label and "互相关注" not in label and "新关注" not in label:
                match = re.search(r'(\d+).*关注', label)
                if match:
                    info["following"] = int(match.group(1))
                    logger.info(f"关注数: {label}")

            # 查找获赞
            elif "获赞" in label:
                match = re.search(r'(\d+).*获赞', label)
                if match:
                    info["likes"] = int(match.group(1))
                    logger.info(f"获赞数: {label}")

            # 查找简介
            elif len(label) > 10 and "@" not in label and "粉丝" not in label and "关注" not in label and "获赞" not in label:
                if not info["bio"] or len(label) > len(info["bio"]):
                    info["bio"] = label

        logger.success(f"提取完成: {info}")
        return {"status": "extracted", "info": info}

    def _screenshot(self) -> Dict[str, Any]:
        """截图"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path("screenshots") / f"screenshot_{timestamp}.png"
        path.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            ["agent-device", "screenshot", str(path), "--json"],
            capture_output=True,
            timeout=10
        )

        logger.info(f"截图已保存: {path}")
        return {"status": "screenshot_saved", "path": str(path)}

    def get_current_state(self) -> Dict[str, Any]:
        """获取当前状态(快照)"""
        snapshot = self.device.get_snapshot()
        return {"snapshot": snapshot, "timestamp": time.time()}
