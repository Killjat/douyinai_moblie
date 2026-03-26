#!/usr/bin/env python3
"""点击'我'按钮获取个人主页"""
import sys
import json
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.device_controller import DeviceController
import re

device = DeviceController()

print("点击'我'按钮...")
snapshot = device.get_snapshot()
nodes = snapshot.get('nodes', [])

# 查找纯"我"字的节点
me_nodes = [n for n in nodes if n.get('label', '').strip() == '我']

if me_nodes:
    ref = me_nodes[0].get('ref')
    print(f"找到'我'按钮: {ref}")
    device.press(ref)
    print("已点击")
    time.sleep(2)

    # 获取新的快照
    print("获取新快照...")
    snapshot = device.get_snapshot()
    nodes = snapshot.get('nodes', [])

    # 保存
    output = Path('output/real_profile.json')
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(f"快照已保存到: {output}")

    # 查找粉丝、关注
    print("\n查找信息:")
    found = False
    for n in nodes:
        label = n.get('label', '')
        if label and len(label) < 50:
            if '粉丝' in label and '关注' not in label and '新关注' not in label:
                m = re.search(r'(\d+).*粉丝', label)
                if m:
                    print(f"  粉丝: {label}")
                    found = True
            elif '关注' in label and '粉丝' not in label and '互相关注' not in label and '新关注' not in label:
                m = re.search(r'(\d+).*关注', label)
                if m:
                    print(f"  关注: {label}")
                    found = True
            elif '获赞' in label:
                m = re.search(r'(\d+).*获赞', label)
                if m:
                    print(f"  获赞: {label}")
                    found = True
            elif '@' in label and label.count('@') == 1 and len(label) < 30:
                print(f"  昵称: {label}")
                found = True

    if not found:
        print("未找到粉丝/关注信息")
        print("前20个有文本的节点:")
        count = 0
        for n in nodes:
            label = n.get('label', '').strip()
            if label:
                count += 1
                if count <= 20:
                    print(f"  {count}. [{n.get('ref')}] {label[:50]}")
else:
    print("未找到'我'按钮")
