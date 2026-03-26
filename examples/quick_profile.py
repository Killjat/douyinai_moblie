#!/usr/bin/env python3
"""快速获取个人主页信息"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.device_controller import DeviceController
import subprocess
import time

device = DeviceController()

print("步骤1: 返回首页...")
subprocess.run(["agent-device", "home", "--json"], capture_output=True, timeout=5)
time.sleep(1.5)

print("步骤2: 获取快照并查找'我'按钮...")
snapshot = device.get_snapshot()
nodes = snapshot.get("nodes", [])

me_nodes = [n for n in nodes if n.get("label", "").strip() == "我"]
if me_nodes:
    print(f"找到'我'按钮: {me_nodes[0].get('ref')}")
    device.press(me_nodes[0].get("ref"))
    time.sleep(2)

print("步骤3: 获取个人主页快照...")
snapshot = device.get_snapshot()
nodes = snapshot.get("nodes", [])

print(f"节点总数: {len(nodes)}")

# 保存完整快照
output = Path("output/snapshot_profile.json")
output.parent.mkdir(exist_ok=True)
with open(output, "w", encoding="utf-8") as f:
    json.dump(snapshot, f, ensure_ascii=False, indent=2)
print(f"快照已保存到: {output}")

# 查找关键信息
info = {"name": "", "followers": 0, "following": 0, "likes": 0}
import re

for node in nodes:
    label = node.get("label", "")
    if label:
        if "@" in label and not info["name"] and label.count("@") == 1:
            info["name"] = label
        elif "粉丝" in label and "关注" not in label:
            m = re.search(r'(\d+).*粉丝', label)
            if m: info["followers"] = int(m.group(1))
        elif "关注" in label and "粉丝" not in label:
            m = re.search(r'(\d+).*关注', label)
            if m: info["following"] = int(m.group(1))
        elif "获赞" in label:
            m = re.search(r'(\d+).*获赞', label)
            if m: info["likes"] = int(m.group(1))

print("\n个人主页信息:")
print(json.dumps(info, ensure_ascii=False, indent=2))
