"""
命令行接口
"""
import click
import json
from pathlib import Path
from loguru import logger
from apps.douyin.client import DouyinClient
from cli.ai_commands import ai


def setup_logging():
    """配置日志"""
    import sys
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG"
    )


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """AI Mobile Control - 手机自动化控制工具"""
    setup_logging()

# 添加 AI 子命令
cli.add_command(ai)


@cli.command()
@click.option("--device", "-d", help="设备 ID")
def check(device):
    """检查设备连接状态"""
    from core.adb_manager import ADBManager
    adb = ADBManager()

    if adb.is_device_connected():
        devices = adb.get_devices()
        logger.success(f"已连接设备: {devices}")
    else:
        logger.error("没有找到已连接的设备")


@cli.command()
@click.option("--device", "-d", help="设备 ID")
def open_douyin(device):
    """打开抖音应用"""
    client = DouyinClient(device)
    if client.open_douyin():
        logger.success("抖音已打开")
    else:
        logger.error("打开抖音失败")


@cli.command()
@click.option("--device", "-d", help="设备 ID")
@click.option("--output", "-o", help="输出文件路径")
def followers(device, output):
    """获取粉丝信息"""
    client = DouyinClient(device)

    # 获取粉丝数量
    count = client.get_follower_count()
    logger.info(f"粉丝数: {count['followers']}, 关注数: {count['following']}")

    # 获取粉丝列表
    followers_list = client.extract_followers_list()
    logger.info(f"提取到 {len(followers_list)} 个粉丝")

    # 输出结果
    result = {
        "count": count,
        "followers": followers_list
    }

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.success(f"结果已保存到: {output}")
    else:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))


@cli.command()
@click.option("--device", "-d", help="设备 ID")
def profile(device):
    """获取个人主页信息"""
    client = DouyinClient(device)
    info = client.get_profile_info()

    click.echo(json.dumps(info, ensure_ascii=False, indent=2))
    logger.success("个人主页信息获取完成")


@cli.command()
@click.option("--device", "-d", help="设备 ID")
@click.option("--bio", "-b", help="简介内容")
def edit_bio(device, bio):
    """编辑个人简介"""
    from config.settings import settings

    if not bio:
        bio = settings.CYBERSTROLL_BIO

    client = DouyinClient(device)
    if client.edit_profile_bio(bio):
        logger.success("简介更新成功")
    else:
        logger.error("简介更新失败")


@cli.command()
@click.option("--device", "-d", help="设备 ID")
def snapshot(device):
    """获取当前屏幕快照"""
    client = DouyinClient(device)
    snapshot = client.get_snapshot()
    analysis = client.device.analyze_snapshot()

    click.echo(f"总节点数: {analysis['total_nodes']}")
    click.echo(f"文本列表: {analysis['texts'][:20]}...")

    # 保存快照
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path("output") / f"snapshot_{timestamp}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    logger.success(f"快照已保存到: {output_path}")


if __name__ == "__main__":
    cli()
