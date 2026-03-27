"""
agent-device 设备控制器
"""
import subprocess
import json
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from loguru import logger


class DeviceController:
    """agent-device 设备控制器"""

    def __init__(self, device_id: Optional[str] = None):
        """初始化设备控制器

        Args:
            device_id: 设备 ID，如果为 None 则使用默认设备
        """
        self.device_id = device_id or self._get_default_device()
        logger.info(f"初始化设备控制器: {self.device_id}")

    def _get_default_device(self) -> str:
        """获取默认设备 ID"""
        result = subprocess.run(
            ["agent-device", "devices", "--json"],
            capture_output=True,
            text=True,
            timeout=10
        )

        # 尝试解析 JSON
        try:
            response = json.loads(result.stdout)

            # agent-device devices 命令返回格式: {"success": true, "data": {"devices": [...]}}
            if isinstance(response, dict):
                devices = response.get("data", {}).get("devices", [])
            elif isinstance(response, list):
                devices = response
            else:
                devices = []

            if not devices:
                raise RuntimeError("没有找到已连接的设备")

            # 返回第一个设备的 id (Android) 或 udid (iOS)
            first_device = devices[0]
            if isinstance(first_device, dict):
                # 优先返回 id (Android) 或 udid (iOS)
                return first_device.get("id") or first_device.get("serial") or first_device.get("udid") or str(first_device)
            return str(first_device)

        except json.JSONDecodeError:
            # 如果不是 JSON，使用第一个行
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    return line.strip()
            raise RuntimeError("没有找到已连接的设备")

    def get_snapshot(self, wait_for_stable: bool = True) -> Dict[str, Any]:
        """获取设备当前屏幕快照

        Args:
            wait_for_stable: 是否等待屏幕稳定

        Returns:
            屏幕快照数据
        """
        cmd = ["agent-device", "snapshot", "--json"]
        # 不要在 session 已绑定时指定 --device 参数
        # if self.device_id:
        #     cmd.extend(["--device", self.device_id])

        logger.debug(f"执行命令: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=40  # 增加超时时间到 40 秒，直播间节点多
        )

        logger.debug(f"命令返回码: {result.returncode}")
        logger.debug(f"命令 stdout 长度: {len(result.stdout)}")

        if result.returncode != 0:
            logger.error(f"获取快照失败 (返回码 {result.returncode})")
            logger.error(f"stdout: {result.stdout[:500]}")
            logger.error(f"stderr: {result.stderr}")
            # 不抛出异常，返回空字典
            return {"nodes": []}

        if not result.stdout:
            logger.error("获取快照失败: 输出为空")
            return {"nodes": []}

        try:
            # agent-device snapshot 返回格式: {"success": true, "data": {...}}
            response = json.loads(result.stdout)
            return response.get("data", response)
        except json.JSONDecodeError as e:
            logger.error(f"解析快照 JSON 失败: {e}, 输出: {result.stdout[:200]}")
            return {"nodes": []}

    def execute_actions(self, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """执行动作序列

        Args:
            actions: 动作列表，每个动作是一个字典

        Returns:
            执行结果
        """
        # 使用 batch 命令执行多个操作
        cmd = ["agent-device", "batch", "--steps", json.dumps(actions), "--json"]
        # 不要在 session 已绑定时指定 --device 参数
        # if self.device_id:
        #     cmd.extend(["--device", self.device_id])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"执行动作失败: {result.stderr}")
            raise RuntimeError(f"执行动作失败: {result.stderr}")

        # agent-device batch 返回格式: {"success": true, "data": {...}}
        response = json.loads(result.stdout)
        return response.get("data", response)

    def press(self, ref: str) -> Dict[str, Any]:
        """点击元素

        Args:
            ref: 元素引用，如 e123 或 @e123

        Returns:
            执行结果
        """
        # 确保 ref 格式正确（添加 @ 前缀）
        if not ref.startswith("@"):
            ref = f"@{ref}"

        cmd = ["agent-device", "click", ref, "--json"]
        # 不要在 session 已绑定时指定 --device 参数
        # if self.device_id:
        #     cmd.extend(["--device", self.device_id])

        logger.debug(f"执行点击命令: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.error(f"点击失败 (返回码 {result.returncode}): {result.stderr}")
            return {}

        try:
            response = json.loads(result.stdout)
            return response.get("data", response)
        except json.JSONDecodeError:
            logger.error(f"解析点击结果失败: {result.stdout[:200]}")
            return {}

    def press_text(self, text: str) -> Optional[Dict[str, Any]]:
        """点击包含指定文本的元素

        Args:
            text: 要查找的文本

        Returns:
            执行结果，如果未找到则返回 None
        """
        snapshot = self.get_snapshot()
        nodes = snapshot.get("nodes", [])

        for node in nodes:
            label = node.get("label", "")
            # 精确匹配文本
            if label.strip() == text.strip():
                ref = node.get("ref")
                logger.info(f"找到元素: {ref} - {label}")
                return self.press(ref)

        logger.warning(f"未找到精确匹配文本 '{text}' 的元素")
        return None

    def press_by_ref(self, ref: str) -> Dict[str, Any]:
        """通过 ref 点击元素

        Args:
            ref: 元素引用

        Returns:
            执行结果
        """
        return self.press(ref)

    def long_press(self, ref: str, duration: int = 1000) -> Dict[str, Any]:
        """长按元素

        Args:
            ref: 元素引用
            duration: 长按持续时间(毫秒)

        Returns:
            执行结果
        """
        action = {"type": "longPress", "ref": ref, "duration": duration}
        return self.execute_actions([action])

    def find_element_by_text(self, text: str) -> Optional[Dict[str, Any]]:
        """通过文本查找元素

        Args:
            text: 要查找的文本

        Returns:
            找到的元素信息，未找到则返回 None
        """
        snapshot = self.get_snapshot()
        nodes = snapshot.get("nodes", [])

        for node in nodes:
            if text in node.get("label", ""):
                logger.info(f"找到元素: {node.get('ref')} - {node.get('label', '')}")
                return node

        logger.warning(f"未找到包含文本 '{text}' 的元素")
        return None

    def analyze_snapshot(self) -> Dict[str, Any]:
        """分析快照结构

        Returns:
            分析结果
        """
        snapshot = self.get_snapshot()
        nodes = snapshot.get("nodes", [])

        analysis = {
            "total_nodes": len(nodes),
            "texts": [],
            "refs": {}
        }

        for node in nodes:
            label = node.get("label", "")
            ref = node.get("ref", "")

            if label:
                analysis["texts"].append(label)

            if ref:
                analysis["refs"][ref] = {
                    "label": label,
                    "type": node.get("type", ""),
                    "visible": node.get("visible", False)
                }

        return analysis

    def wait_for_element(self, text: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """等待元素出现

        Args:
            text: 要等待的元素文本
            timeout: 超时时间(秒)

        Returns:
            找到的元素，超时则返回 None
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            element = self.find_element_by_text(text)
            if element:
                return element
            time.sleep(0.5)

        logger.error(f"等待元素 '{text}' 超时")
        return None
