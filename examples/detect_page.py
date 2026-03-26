#!/usr/bin/env python3
"""检测当前页面状态"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.device_controller import DeviceController

print("=" * 50)
print("检测当前页面状态")
print("=" * 50)

device = DeviceController()

# 获取当前快照
print("\n获取当前屏幕快照...")
snapshot = device.get_snapshot()
nodes = snapshot.get("nodes", [])

print(f"节点总数: {len(nodes)}")

# 分析当前页面
print("\n分析当前页面状态:")

# 1. 检查是否在桌面(华为启动器)
launcher_nodes = [n for n in nodes if "huawei.android.launcher" in n.get("identifier", "")]
if launcher_nodes:
    print("  ✅ 当前在: 手机桌面 (华为启动器)")

# 2. 检查是否在抖音
douyin_nodes = [n for n in nodes if "com.ss.android.ugc.aweme" in n.get("identifier", "")]
if douyin_nodes:
    print("  ✅ 当前在: 抖音应用")

    # 检查抖音内具体页面
    # 找底部导航栏
    bottom_nav_keywords = ["首页", "朋友", "消息", "我", "拍摄"]
    found_nav = []
    for keyword in bottom_nav_keywords:
        nav_nodes = [n for n in nodes if n.get("label", "").strip() == keyword]
        if nav_nodes:
            found_nav.append(keyword)

    if found_nav:
        print(f"  📍 发现底部导航: {', '.join(found_nav)}")

    # 检查"我"标签页
    me_nodes = [n for n in nodes if n.get("label", "").strip() == "我"]
    if len(me_nodes) > 0:
        print("  📍 找到'我'按钮")

    # 检查是否在个人主页(有粉丝、关注等)
    has_fans = any("粉丝" in n.get("label", "") for n in nodes)
    has_following = any("关注" in n.get("label", "") and "粉丝" not in n.get("label", "") for n in nodes)

    if has_fans or has_following:
        print("  ✅ 当前在: 抖音个人主页")

# 3. 显示前20个有文本的节点
print("\n前20个有文本的节点:")
text_nodes = [n for n in nodes if n.get("label", "").strip()]
for i, node in enumerate(text_nodes[:20]):
    label = node.get("label", "")[:50]
    print(f"  {i+1}. [{node.get('ref')}] {label}")

# 保存快照
output = Path("output/current_page_snapshot.json")
output.parent.mkdir(exist_ok=True)
with open(output, "w", encoding="utf-8") as f:
    json.dump(snapshot, f, ensure_ascii=False, indent=2)
print(f"\n完整快照已保存到: {output}")
