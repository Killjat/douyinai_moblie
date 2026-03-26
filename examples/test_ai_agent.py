#!/usr/bin/env python3
"""测试 AI 智能代理"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_brain.ai_agent import create_agent


def main():
    """测试 AI 智能代理"""

    # 创建 AI 代理
    agent = create_agent()

    # 执行任务
    task = "获取抖音个人主页信息"
    result = agent.execute_task(task)

    # 显示结果
    print("\n" + "=" * 70)
    print("任务执行结果")
    print("=" * 70)
    print(f"任务: {result['task']}")
    print(f"完成: {result['completed']}")
    print(f"执行步数: {result['steps_executed']}")
    print(f"日志文件: 见 output/ 目录")

    if result['completed']:
        print("\n✅ 任务成功完成!")
    else:
        print("\n⚠️  任务未完成")


if __name__ == "__main__":
    main()
