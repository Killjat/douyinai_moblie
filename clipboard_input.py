#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用剪贴板方式输入中文到Android
"""
import subprocess
import pyperclip

def input_via_clipboard(text):
    """通过剪贴板输入文本"""
    try:
        # 复制到剪贴板
        pyperclip.copy(text)
        print(f"✅ 已复制到剪贴板: {text}")

        # 在Android设备上粘贴
        subprocess.run(['adb', 'shell', 'input', 'keyevent', 'KEYCODE_PASTE'],
                     capture_output=True, text=True)
        print("✅ 已粘贴到Android设备")
        return True
    except ImportError:
        print("⚠️ 需要安装 pyperclip: pip3 install pyperclip")
        return False
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 clipboard_input.py '要输入的文本'")
        sys.exit(1)

    text = sys.argv[1]
    input_via_clipboard(text)
