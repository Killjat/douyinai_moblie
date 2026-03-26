#!/usr/bin/env python3
"""
AI Mobile Control 使用示例
"""
from ai_mobile_control import main
from apps.douyin.client import DouyinClient
from loguru import logger


def example_check_device():
    """示例1: 检查设备连接"""
    logger.info("=== 检查设备连接 ===")
    from core.adb_manager import ADBManager

    adb = ADBManager()
    if adb.is_device_connected():
        devices = adb.get_devices()
        logger.success(f"已连接设备: {devices}")
    else:
        logger.error("没有找到已连接的设备")


def example_open_douyin():
    """示例2: 打开抖音"""
    logger.info("=== 打开抖音 ===")
    client = DouyinClient()
    if client.open_douyin():
        logger.success("抖音已打开")
    else:
        logger.error("打开抖音失败")


def example_get_followers():
    """示例3: 获取粉丝信息"""
    logger.info("=== 获取粉丝信息 ===")
    client = DouyinClient()

    # 获取粉丝数量
    count = client.get_follower_count()
    logger.info(f"粉丝数: {count['followers']}, 关注数: {count['following']}")

    # 获取粉丝列表
    followers_list = client.extract_followers_list()
    logger.info(f"提取到 {len(followers_list)} 个粉丝")

    for follower in followers_list:
        logger.info(f"  - {follower['name']}")


def example_get_profile():
    """示例4: 获取个人主页信息"""
    logger.info("=== 获取个人主页信息 ===")
    client = DouyinClient()
    info = client.get_profile_info()

    logger.info(f"昵称: {info['name']}")
    logger.info(f"粉丝: {info['followers']}")
    logger.info(f"关注: {info['following']}")
    logger.info(f"获赞: {info['likes']}")


def example_edit_bio():
    """示例5: 编辑个人简介"""
    logger.info("=== 编辑个人简介 ===")
    from config.settings import settings

    client = DouyinClient()
    bio = settings.CYBERSTROLL_BIO

    if client.edit_profile_bio(bio):
        logger.success("简介更新成功")
    else:
        logger.error("简介更新失败")


def example_get_snapshot():
    """示例6: 获取屏幕快照"""
    logger.info("=== 获取屏幕快照 ===")
    from core.device_controller import DeviceController
    import json
    from datetime import datetime
    from pathlib import Path

    device = DeviceController()
    snapshot = device.get_snapshot()
    analysis = device.analyze_snapshot()

    logger.info(f"总节点数: {analysis['total_nodes']}")
    logger.info(f"前20个文本: {analysis['texts'][:20]}")

    # 保存快照
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path("output") / f"snapshot_{timestamp}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    logger.success(f"快照已保存到: {output_path}")


if __name__ == "__main__":
    import sys

    # 根据命令行参数运行不同示例
    if len(sys.argv) > 1:
        example_name = sys.argv[1]

        if example_name == "check":
            example_check_device()
        elif example_name == "open":
            example_open_douyin()
        elif example_name == "followers":
            example_get_followers()
        elif example_name == "profile":
            example_get_profile()
        elif example_name == "bio":
            example_edit_bio()
        elif example_name == "snapshot":
            example_get_snapshot()
        else:
            logger.error(f"未知的示例: {example_name}")
            logger.info("可用示例: check, open, followers, profile, bio, snapshot")
    else:
        # 默认运行所有示例
        example_check_device()
        example_open_douyin()
        example_get_profile()
        example_get_followers()
