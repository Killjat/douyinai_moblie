#!/usr/bin/env python3
"""智能获取抖音个人主页 - 自动判断当前页面并执行相应操作"""
import sys
import json
import subprocess
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.device_controller import DeviceController
from loguru import logger

def detect_current_page(device):
    """检测当前页面

    Returns:
        str: 页面类型 (desktop, douyin_home, douyin_profile, douyin_other)
    """
    snapshot = device.get_snapshot()
    nodes = snapshot.get("nodes", [])

    # 检查桌面
    launcher_nodes = [n for n in nodes if "huawei.android.launcher" in n.get("identifier", "")]
    if launcher_nodes:
        return "desktop"

    # 检查抖音
    douyin_nodes = [n for n in nodes if "com.ss.android.ugc.aweme" in n.get("identifier", "")]
    if douyin_nodes:
        # 检查是否在个人主页
        has_fans = any("粉丝" in n.get("label", "") and len(n.get("label", "")) < 20 for n in nodes)
        if has_fans:
            return "douyin_profile"

        # 检查是否有底部导航
        has_nav = any(n.get("label", "").strip() in ["首页", "朋友", "消息", "我"] for n in nodes)
        if has_nav:
            return "douyin_home"

        return "douyin_other"

    return "unknown"

def get_profile_info(device):
    """获取个人主页信息"""
    snapshot = device.get_snapshot()
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

        # 查找粉丝 (排除"新关注我的"等提示)
        elif "粉丝" in label and "新关注" not in label and "关注" not in label:
            match = re.search(r'(\d+).*粉丝', label)
            if match:
                info["followers"] = int(match.group(1))
                logger.info(f"粉丝数: {label}")

        # 查找关注 (排除"互相关注"等提示)
        elif "关注" in label and "粉丝" not in label and "互相关注" not in label:
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

    return info

def navigate_to_profile(device):
    """导航到个人主页"""
    logger.info("导航到个人主页...")

    # 1. 获取快照查找"我"按钮
    snapshot = device.get_snapshot()
    nodes = snapshot.get("nodes", [])

    # 查找纯"我"字的节点
    me_nodes = [
        node for node in nodes
        if node.get("label", "").strip() == "我"
    ]

    if me_nodes:
        ref = me_nodes[0].get("ref")
        logger.info(f"找到'我'按钮: {ref}")
        device.press(ref)
        time.sleep(2.5)
        return True
    else:
        logger.warning("未找到'我'按钮")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("智能获取抖音个人主页信息")
    print("=" * 60)

    device = DeviceController()

    # 步骤1: 检测当前页面
    print("\n[步骤1] 检测当前页面...")
    current_page = detect_current_page(device)
    print(f"当前页面: {current_page}")

    # 步骤2: 根据当前页面执行不同操作
    print("\n[步骤2] 根据当前页面执行操作...")

    if current_page == "desktop":
        print("  在桌面,需要打开抖音")
        logger.info("打开抖音应用...")
        subprocess.run(
            ["agent-device", "open", "com.ss.android.ugc.aweme", "--json"],
            capture_output=True,
            timeout=15
        )
        time.sleep(2)
        navigate_to_profile(device)

    elif current_page == "douyin_home":
        print("  在抖音首页,导航到个人主页")
        navigate_to_profile(device)

    elif current_page == "douyin_profile":
        print("  已在个人主页,直接获取信息")

    elif current_page == "douyin_other":
        print("  在抖音其他页面,返回首页再导航")
        subprocess.run(["agent-device", "home", "--json"], capture_output=True, timeout=10)
        time.sleep(1)
        subprocess.run(
            ["agent-device", "open", "com.ss.android.ugc.aweme", "--json"],
            capture_output=True,
            timeout=15
        )
        time.sleep(2)
        navigate_to_profile(device)

    else:
        print("  未知页面,尝试返回首页")
        subprocess.run(["agent-device", "home", "--json"], capture_output=True, timeout=10)
        time.sleep(1)
        subprocess.run(
            ["agent-device", "open", "com.ss.android.ugc.aweme", "--json"],
            capture_output=True,
            timeout=15
        )
        time.sleep(2)
        navigate_to_profile(device)

    # 步骤3: 获取个人主页信息
    print("\n[步骤3] 获取个人主页信息...")
    info = get_profile_info(device)

    # 保存快照
    snapshot = device.get_snapshot()
    output = Path("output/profile_info.json")
    output.parent.mkdir(exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump({
            "profile": info,
            "snapshot": snapshot
        }, f, ensure_ascii=False, indent=2)

    # 显示结果
    print("\n" + "=" * 60)
    print("个人主页信息")
    print("=" * 60)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    print(f"\n详细信息已保存到: {output}")

if __name__ == "__main__":
    main()
