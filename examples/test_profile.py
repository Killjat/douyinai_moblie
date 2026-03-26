#!/usr/bin/env python3
"""
测试获取个人主页信息
"""
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.device_controller import DeviceController
from loguru import logger


def test_get_profile():
    """测试获取个人主页信息"""
    device = DeviceController()

    # 获取当前快照
    logger.info("获取当前屏幕快照...")
    snapshot = device.get_snapshot()
    nodes = snapshot.get("nodes", [])

    logger.info(f"节点总数: {len(nodes)}")

    # 查找包含"我"的节点
    me_nodes = [node for node in nodes if "我" in node.get("label", "")]
    logger.info(f"找到 {len(me_nodes)} 个包含'我'的节点")

    for node in me_nodes[:5]:  # 只显示前5个
        logger.info(f"  ref: {node.get('ref')}, label: {node.get('label')}")

    # 查找包含"粉丝"的节点
    followers_nodes = [node for node in nodes if "粉丝" in node.get("label", "")]
    logger.info(f"找到 {len(followers_nodes)} 个包含'粉丝'的节点")

    for node in followers_nodes[:5]:
        logger.info(f"  ref: {node.get('ref')}, label: {node.get('label')}")

    # 查找包含"关注"的节点
    following_nodes = [node for node in nodes if "关注" in node.get("label", "")]
    logger.info(f"找到 {len(following_nodes)} 个包含'关注'的节点")

    for node in following_nodes[:5]:
        logger.info(f"  ref: {node.get('ref')}, label: {node.get('label')}")


if __name__ == "__main__":
    test_get_profile()
