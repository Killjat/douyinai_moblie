"""
操作录制器
记录用户的操作序列并生成可回放的代码
"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger


class ActionRecorder:
    """操作录制器"""

    def __init__(self, record_dir: str = "recordings"):
        """初始化录制器

        Args:
            record_dir: 录制文件保存目录
        """
        self.record_dir = Path(record_dir)
        self.record_dir.mkdir(parents=True, exist_ok=True)

        self.is_recording = False
        self.actions: List[Dict[str, Any]] = []
        self.start_time: Optional[float] = None
        self.last_snapshot: Optional[Dict[str, Any]] = None

    def start(self) -> str:
        """开始录制

        Returns:
            录制会话 ID
        """
        if self.is_recording:
            logger.warning("录制已在进行中")
            return ""

        self.is_recording = True
        self.actions = []
        self.start_time = time.time()
        self.last_snapshot = None

        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"开始录制会话: {session_id}")

        return session_id

    def stop(self) -> str:
        """停止录制并保存

        Returns:
            保存的文件路径
        """
        if not self.is_recording:
            logger.warning("没有正在进行的录制")
            return ""

        self.is_recording = False

        # 保存录制结果
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{session_id}.json"
        filepath = self.record_dir / filename

        recording_data = {
            "session_id": session_id,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration": time.time() - self.start_time,
            "actions": self.actions
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(recording_data, f, ensure_ascii=False, indent=2)

        logger.info(f"录制已保存到: {filepath}")
        logger.info(f"共记录 {len(self.actions)} 个操作")

        return str(filepath)

    def add_action(self, action_type: str, **kwargs) -> None:
        """添加一个操作

        Args:
            action_type: 操作类型 (click, swipe, back, input_text, etc.)
            **kwargs: 操作参数
        """
        if not self.is_recording:
            logger.warning("未在录制中，无法添加操作")
            return

        action = {
            "timestamp": time.time() - self.start_time,
            "type": action_type,
            **kwargs
        }

        self.actions.append(action)
        logger.debug(f"添加操作: {action_type}")

    def detect_changes(self, current_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检测快照变化，推断用户操作

        Args:
            current_snapshot: 当前屏幕快照

        Returns:
            检测到的操作列表
        """
        if self.last_snapshot is None:
            self.last_snapshot = current_snapshot
            return []

        detected_actions = []

        # 获取当前和之前的节点
        current_nodes = current_snapshot.get("nodes", [])
        previous_nodes = self.last_snapshot.get("nodes", [])

        # 简单的变化检测（实际应用中需要更复杂的算法）
        current_refs = {node.get("ref"): node for node in current_nodes}
        previous_refs = {node.get("ref"): node for node in previous_nodes}

        # 检测新出现的可点击元素（可能被点击了）
        for ref, current_node in current_refs.items():
            if ref in previous_refs:
                prev_node = previous_refs[ref]

                # 检查可见性变化
                current_visible = current_node.get("visible", False)
                prev_visible = prev_node.get("visible", False)

                if current_visible and not prev_visible:
                    # 元素刚刚变为可见，可能是一个页面跳转的结果
                    pass
                elif not current_visible and prev_visible:
                    # 元素刚刚消失，可能被点击
                    if prev_node.get("type") in ["Button", "View", "Text"]:
                        detected_actions.append({
                            "type": "click",
                            "ref": ref,
                            "text": prev_node.get("label", ""),
                            "inferred": True
                        })

        self.last_snapshot = current_snapshot
        return detected_actions

    def generate_code(self, recording_path: str, output_path: Optional[str] = None) -> str:
        """根据录制生成 Python 代码

        Args:
            recording_path: 录制文件路径
            output_path: 输出文件路径，如果为 None 则返回代码字符串

        Returns:
            生成的代码字符串
        """
        # 读取录制文件
        with open(recording_path, "r", encoding="utf-8") as f:
            recording_data = json.load(f)

        actions = recording_data.get("actions", [])

        # 生成代码
        code_lines = [
            '"""',
            f'自动生成的操作脚本',
            f'录制时间: {recording_data.get("start_time", "")}',
            f'操作数量: {len(actions)}',
            '"""',
            '',
            'import time',
            'from apps.douyin.client import DouyinClient',
            '',
            '',
            'def run_automation(device_id: str = None):',
            '    """执行自动化操作"""',
            '    client = DouyinClient(device_id)',
            '    ',
        ]

        for i, action in enumerate(actions):
            action_type = action.get("type")

            if action_type == "click":
                ref = action.get("ref", "")
                text = action.get("text", "")
                code_lines.append(f'    # 步骤 {i+1}: 点击 "{text}"')
                code_lines.append(f'    client.device.press("{ref}")')
                code_lines.append(f'    time.sleep(0.5)  # 等待页面响应')
                code_lines.append('')

            elif action_type == "click_by_text":
                text = action.get("text", "")
                code_lines.append(f'    # 步骤 {i+1}: 点击文本 "{text}"')
                code_lines.append(f'    client.device.press_text("{text}")')
                code_lines.append(f'    time.sleep(0.5)  # 等待页面响应')
                code_lines.append('')

            elif action_type == "back":
                code_lines.append(f'    # 步骤 {i+1}: 返回')
                code_lines.append('    client.device.press_key("KEYCODE_BACK")')
                code_lines.append('    time.sleep(0.5)')
                code_lines.append('')

            elif action_type == "input_text":
                text = action.get("text", "")
                code_lines.append(f'    # 步骤 {i+1}: 输入文本')
                code_lines.append(f'    client.device.input_text("{text}")')
                code_lines.append('    time.sleep(0.3)')
                code_lines.append('')

            elif action_type == "swipe":
                x1, y1, x2, y2 = action.get("x1", 0), action.get("y1", 0), action.get("x2", 0), action.get("y2", 0)
                code_lines.append(f'    # 步骤 {i+1}: 滑动')
                code_lines.append(f'    client.device.swipe({x1}, {y1}, {x2}, {y2})')
                code_lines.append('    time.sleep(0.5)')
                code_lines.append('')

            else:
                code_lines.append(f'    # 步骤 {i+1}: 未知操作 {action_type}')
                code_lines.append('    pass')
                code_lines.append('')

        code_lines.extend([
            '',
            '    logger.success("自动化操作完成")',
            '',
            '',
            'if __name__ == "__main__":',
            '    run_automation()'
        ])

        code = '\n'.join(code_lines)

        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(code)
            logger.info(f"代码已保存到: {output_path}")

        return code
