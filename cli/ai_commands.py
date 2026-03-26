"""
AI 智能命令 - DeepSeek 大脑驱动的自动化
"""
import click
import json
from pathlib import Path
from loguru import logger

from ai_brain.ai_agent import create_agent


@click.group()
def ai():
    """AI 智能命令 - DeepSeek 大脑驱动的自动化"""
    pass


@ai.command()
@click.argument("task")
@click.option("--device", "-d", help="设备 ID")
@click.option("--api-key", help="DeepSeek API Key")
@click.option("--max-steps", "-m", default=20, help="最大执行步数")
def execute(task, device, api_key, max_steps):
    """使用 AI 智能执行任务

    Example:
        ai execute "获取抖音个人主页信息"
        ai execute "打开抖音并查看粉丝列表"
    """
    logger.info(f"AI 智能执行: {task}")

    # 创建 AI 代理
    agent = create_agent(device_id=device, api_key=api_key)

    # 执行任务
    result = agent.execute_task(task, max_steps=max_steps)

    # 显示结果
    if result["completed"]:
        logger.success(f"✅ 任务成功完成!")
    else:
        logger.warning(f"⚠️  任务未完成,执行了 {result['steps_executed']} 步")

    # 显示最终信息
    click.echo("\n" + "=" * 70)
    click.echo("执行摘要")
    click.echo("=" * 70)
    click.echo(f"任务: {result['task']}")
    click.echo(f"完成状态: {result['completed']}")
    click.echo(f"执行步数: {result['steps_executed']}")
    click.echo(f"日志文件: 见 output/ 目录")


@ai.command()
@click.option("--device", "-d", help="设备 ID")
@click.option("--api-key", help="DeepSeek API Key")
def interactive(device, api_key):
    """交互式 AI 助手 - 持续对话执行任务"""
    agent = create_agent(device_id=device, api_key=api_key)
    agent.interactive_mode()


@ai.command()
@click.option("--device", "-d", help="设备 ID")
def analyze(device):
    """分析当前屏幕并给出建议"""
    from core.executor import Executor

    executor = Executor(device_id=device)
    state = executor.get_current_state()

    # 使用 AI 分析
    from ai_brain.deepseek_client import DeepSeekBrain
    brain = DeepSeekBrain()

    analysis = brain.analyze_page(state["snapshot"], "分析当前页面")

    click.echo("\n" + "=" * 70)
    click.echo("当前页面分析")
    click.echo("=" * 70)
    click.echo(f"页面类型: {analysis['page_type']}")
    click.echo(f"当前状态: {analysis['current_state']}")
    click.echo(f"关键元素: {', '.join(analysis['key_elements'])}")
    click.echo(f"建议操作: {analysis['next_step']}")
    click.echo(f"置信度: {analysis['confidence']:.2%}")

    click.echo("\n建议的操作步骤:")
    for i, action in enumerate(analysis['suggested_actions'], 1):
        click.echo(f"  {i}. {action['action']} - {action['target']} ({action['reason']})")


if __name__ == "__main__":
    ai()
