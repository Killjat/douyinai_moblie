#!/usr/bin/env python3
"""
测试点击后获取个人主页信息
"""
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.device_controller import DeviceController
from loguru import logger


def test_click_and_profile():
    """测试点击后获取个人主页信息"""
    device = DeviceController()

    # 获取当前快照
    logger.info("步骤1: 获取当前屏幕快照...")
    snapshot = device.get_snapshot()
    nodes = snapshot.get("nodes", [])

    # 查找纯"我"字的节点
    me_nodes = [
        node for node in nodes
        if node.get("label", "").strip() == "我"
    ]

    if me_nodes:
        me_node = me_nodes[0]
        ref = me_node.get("ref")
        logger.info(f"找到'我'按钮: ref={ref}, label={me_node.get('label')}")

        # 点击"我"按钮
        logger.info("步骤2: 点击'我'按钮...")
        result = device.press(ref)
        logger.info(f"点击结果: {result}")

        # 等待页面加载
        time.sleep(2)

        # 再次获取快照
        logger.info("步骤3: 获取个人主页快照...")
        snapshot = device.get_snapshot()
        nodes = snapshot.get("nodes", [])

        logger.info(f"节点总数: {len(nodes)}")

        # 查找包含"粉丝"、"关注"、"获赞"的节点
        for keyword in ["粉丝", "关注", "获赞"]:
            keyword_nodes = [
                node for node in nodes
                if keyword in node.get("label", "")
            ]
            logger.info(f"找到 {len(keyword_nodes)} 个包含'{keyword}'的节点:")
            for node in keyword_nodes[:3]:
                logger.info(f"  ref: {node.get('ref')}, label: {node.get('label')}")
    else:
        logger.warning("未找到'我'按钮")
        logger.info("当前屏幕可能已在个人主页")

        # 直接查找粉丝、关注、获赞
        for keyword in ["粉丝", "关注", "获赞"]:
            keyword_nodes = [
                node for node in nodes
                if keyword in node.get("label", "")
            ]
            logger.info(f"找到 {len(keyword_nodes)} 个包含'{keyword}'的节点:")
            for node in keyword_nodes[:3]:
                logger.info(f"  ref: {node.get('ref')}, label: {node.get('label')}")


if __name__ == "__main__":
    test_click_and_profile()
