#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import sys

def input_chinese_text(text):
    """使用ADB输入中文"""
    # 尝试使用剪贴板方式
    try:
        # 方法1: 尝试直接输入
        result = subprocess.run(
            ['adb', 'shell', 'input', 'text', text],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ 已输入: {text}")
            return True
    except Exception as e:
        print(f"❌ 方法1失败: {e}")

    # 方法2: 使用编码转换
    try:
        # 将空格转换为 %s
        encoded_text = text.replace(' ', '%s')
        result = subprocess.run(
            ['adb', 'shell', 'input', 'text', encoded_text],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ 已输入: {text}")
            return True
    except Exception as e:
        print(f"❌ 方法2失败: {e}")

    print("⚠️ 自动输入失败，请手动输入")
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python input_chinese.py '要输入的文本'")
        sys.exit(1)

    text = sys.argv[1]
    input_chinese_text(text)
