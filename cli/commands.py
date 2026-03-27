"""
命令行接口
"""
import click
import json
import time
from pathlib import Path
from loguru import logger
from apps.douyin.client import DouyinClient
from cli.ai_commands import ai
from core.recorder import ActionRecorder


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
@click.option("--count", "-n", default=5, show_default=True, help="扫描视频数量")
@click.option("--output", "-o", help="输出文件路径")
def scan_feed(device, count, output):
    """扫描推荐视频流，获取作者、标题和评论"""
    from apps.douyin.features import FeedFeature
    client = DouyinClient(device)
    results = FeedFeature(client).scan(count=count)

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.success(f"结果已保存到: {output}")
    else:
        click.echo(json.dumps(results, ensure_ascii=False, indent=2))


@cli.command()
@click.option("--device", "-d", help="设备 ID")
@click.option("--output", "-o", help="输出文件路径")
def live(device, output):
    """采集当前直播间信息（需先在手机上进入直播间）"""
    from apps.douyin.features import LiveFeature
    import dataclasses
    client = DouyinClient(device)
    result = LiveFeature(client).collect()
    data = dataclasses.asdict(result)
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.success(f"结果已保存到: {output}")
    else:
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))


@cli.command()
@click.option("--device", "-d", help="设备 ID")
@click.option("--output", "-o", help="输出文件路径")
def followers(device, output):
    """获取粉丝信息"""
    from apps.douyin.features import ProfileFeature
    client = DouyinClient(device)
    feature = ProfileFeature(client)

    count = feature.get_follower_count()
    logger.info(f"粉丝数: {count['followers']}, 关注数: {count['following']}")

    followers_list = feature.get_followers_list()
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
    from apps.douyin.features import ProfileFeature
    client = DouyinClient(device)
    info = ProfileFeature(client).get_info()
    click.echo(json.dumps(info, ensure_ascii=False, indent=2))
    logger.success("个人主页信息获取完成")


@cli.command()
@click.option("--device", "-d", help="设备 ID")
@click.option("--bio", "-b", help="简介内容")
def edit_bio(device, bio):
    """编辑个人简介"""
    from apps.douyin.features import ProfileFeature
    from config.settings import settings
    if not bio:
        bio = settings.CYBERSTROLL_BIO
    client = DouyinClient(device)
    if ProfileFeature(client).edit_bio(bio):
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


@cli.command()
@click.option("--device", "-d", help="设备 ID")
@click.option("--interval", "-i", default=1.0, help="检测间隔(秒)")
def record(device, interval):
    """开始录制操作 - 持续监控屏幕变化"""
    import signal
    import sys

    recorder = ActionRecorder()
    client = DouyinClient(device)

    session_id = recorder.start()
    click.echo(f"📹 开始录制会话: {session_id}")
    click.echo(f"📱 按提示在手机上操作...")
    click.echo(f"⏹️  按 Ctrl+C 停止录制")

    # 记录初始快照
    last_snapshot = client.get_snapshot()

    try:
        while True:
            time.sleep(interval)

            # 获取当前快照
            current_snapshot = client.get_snapshot()

            # 检测变化
            changes = recorder.detect_changes(current_snapshot)

            # 如果检测到变化，记录操作
            for change in changes:
                if change.get("type") == "click":
                    recorder.add_action(
                        action_type="click",
                        ref=change.get("ref"),
                        text=change.get("text", ""),
                        inferred=True
                    )
                    click.echo(f"✓ 检测到点击: {change.get('text', '')}")

            last_snapshot = current_snapshot

    except KeyboardInterrupt:
        filepath = recorder.stop()
        click.echo(f"\n✅ 录制完成: {filepath}")
        click.echo(f"📝 共记录 {len(recorder.actions)} 个操作")

        # 询问是否生成代码
        if click.confirm("是否生成可执行代码？"):
            output_file = filepath.replace(".json", ".py")
            recorder.generate_code(filepath, output_file)
            click.echo(f"🚀 代码已生成: {output_file}")
            click.echo(f"执行: python {output_file}")


@cli.command()
@click.option("--device", "-d", help="设备 ID")
@click.option("--output", "-o", help="输出代码文件路径")
def interactive_record(device, output):
    """交互式录制 - 你在手机操作后按回车，我记录并分析"""
    import sys
    import termios
    import tty

    recorder = ActionRecorder()
    client = DouyinClient(device)

    session_id = recorder.start()
    click.echo(f"\n📹 交互式录制模式")
    click.echo("=" * 60)
    click.echo(f"会话 ID: {session_id}")
    click.echo("\n使用方法:")
    click.echo("1. 在手机上执行操作（点击、滑动等）")
    click.echo("2. 按回车键记录当前状态")
    click.echo("3. 输入操作描述（可选，直接回车跳过）")
    click.echo("4. 重复步骤 1-3")
    click.echo("5. 输入 'done' 或按 Ctrl+C 结束")
    click.echo("=" * 60)

    step = 0
    last_snapshot = None

    try:
        while True:
            step += 1
            user_input = click.prompt(f"\n步骤 [{step}] - 执行操作后按回车（输入'done'结束）",
                                     type=str, show_default=False, default="")

            if user_input.lower() in ['done', 'exit', 'quit']:
                break

            # 获取当前快照
            current_snapshot = client.get_snapshot()

            # 检测变化（如果有上一次快照）
            changes = recorder.detect_changes(current_snapshot)

            # 让用户确认或描述操作
            description = click.prompt(f"  描述操作（直接回车自动检测，或输入如 'click 我'）",
                                      type=str, show_default=False, default="")

            if description:
                # 手动输入描述
                parts = description.split()
                if len(parts) >= 2:
                    action_type = parts[0].lower()
                    if action_type == 'click':
                        text = ' '.join(parts[1:])
                        recorder.add_action('click_by_text', text=text, inferred=False)
                        click.echo(f"  ✓ 已记录: 点击 '{text}'")
                    elif action_type == 'back':
                        recorder.add_action('back', inferred=False)
                        click.echo(f"  ✓ 已记录: 返回")
                    elif action_type == 'input':
                        text = ' '.join(parts[1:])
                        recorder.add_action('input_text', text=text, inferred=False)
                        click.echo(f"  ✓ 已记录: 输入 '{text}'")
                    else:
                        click.echo(f"  ✗ 无法识别: {description}")
                        recorder.add_action('manual', description=description, inferred=False)
            elif changes:
                # 自动检测到的变化
                for change in changes:
                    if change.get("type") == "click":
                        recorder.add_action(
                            action_type="click",
                            ref=change.get("ref"),
                            text=change.get("text", ""),
                            inferred=True
                        )
                        click.echo(f"  ✓ 自动检测到: 点击 '{change.get('text', '')}'")
            else:
                # 没有检测到变化，但用户确认了操作
                # 记录快照以便后续分析
                recorder.add_action('snapshot', description="手动记录快照", inferred=False)
                click.echo(f"  ✓ 已记录快照（步骤 {step}）")

            last_snapshot = current_snapshot

    except KeyboardInterrupt:
        pass

    if step == 1 and not recorder.actions:
        click.echo("\n没有记录任何操作")
        return

    filepath = recorder.stop()
    click.echo(f"\n✅ 录制完成: {filepath}")
    click.echo(f"📝 共记录 {len(recorder.actions)} 个操作")

    if not output:
        output = filepath.replace(".json", ".py")

    if click.confirm("是否生成可执行代码？"):
        recorder.generate_code(filepath, output)
        click.echo(f"🚀 代码已生成: {output}")
        click.echo(f"执行: python {output}")


@cli.command()
@click.argument("recording_file", type=click.Path(exists=True))
@click.option("--device", "-d", help="设备 ID")
def replay(recording_file, device):
    """回放录制的操作"""
    client = DouyinClient(device)

    # 读取录制文件
    with open(recording_file, "r", encoding="utf-8") as f:
        recording_data = json.load(f)

    actions = recording_data.get("actions", [])

    click.echo(f"▶️  开始回放: {len(actions)} 个操作")
    click.echo(f"📅 录制时间: {recording_data.get('start_time', '')}")

    success_count = 0
    for i, action in enumerate(actions):
        action_type = action.get("type")
        click.echo(f"[{i+1}/{len(actions)}] {action_type}...", nl=False)

        try:
            if action_type == "click":
                ref = action.get("ref", "")
                result = client.device.press(ref)
                if result:
                    success_count += 1
                    click.echo(f" ✓")
                else:
                    click.echo(f" ✗")
                time.sleep(0.5)

            elif action_type == "click_by_text":
                text = action.get("text", "")
                result = client.device.press_text(text)
                if result:
                    success_count += 1
                    click.echo(f" ✓")
                else:
                    click.echo(f" ✗")
                time.sleep(0.5)

            elif action_type == "back":
                client.device.press_key("KEYCODE_BACK")
                success_count += 1
                click.echo(f" ✓")
                time.sleep(0.5)

            elif action_type == "input_text":
                text = action.get("text", "")
                client.device.input_text(text)
                success_count += 1
                click.echo(f" ✓")
                time.sleep(0.3)

            elif action_type == "swipe":
                x1, y1, x2, y2 = action.get("x1", 0), action.get("y1", 0), action.get("x2", 0), action.get("y2", 0)
                client.device.swipe(x1, y1, x2, y2)
                success_count += 1
                click.echo(f" ✓")
                time.sleep(0.5)

            else:
                click.echo(f" ? (未知类型)")

        except Exception as e:
            click.echo(f" ✗ ({str(e)[:50]})")

    click.echo(f"\n📊 回放完成: {success_count}/{len(actions)} 成功")


@cli.command()
@click.argument("recording_file", type=click.Path(exists=True))
@click.option("--output", "-o", help="输出代码文件路径")
def generate_code(recording_file, output):
    """根据录制生成可执行代码"""
    recorder = ActionRecorder()

    if output:
        recorder.generate_code(recording_file, output)
    else:
        code = recorder.generate_code(recording_file)
        click.echo(code)


@cli.command()
@click.option("--device", "-d", help="设备 ID")
@click.option("--output", "-o", help="输出代码文件路径")
def manual_record(device, output):
    """手动录制 - 交互式描述操作并生成代码"""
    client = DouyinClient(device)

    click.echo("📝 手动录制模式")
    click.echo("=" * 50)
    click.echo("每次输入一个操作，输入 'done' 结束录制")
    click.echo("支持的操作类型:")
    click.echo("  - click <文本>        : 点击包含指定文本的元素")
    click.echo("  - back                : 返回")
    click.echo("  - input <文本>        : 输入文本")
    click.echo("  - swipe <x1> <y1> <x2> <y2> : 滑动")
    click.echo("=" * 50)

    recorder = ActionRecorder()
    recorder.start()

    action_count = 0
    while True:
        action_input = click.prompt(f"\n操作 [{action_count + 1}]", type=str).strip()

        if action_input.lower() in ['done', 'exit', 'quit']:
            break

        if not action_input:
            continue

        parts = action_input.split()
        action_type = parts[0].lower()

        if action_type == 'click' and len(parts) >= 2:
            text = ' '.join(parts[1:])
            recorder.add_action('click_by_text', text=text, inferred=False)
            click.echo(f"✓ 添加操作: 点击 '{text}'")
            action_count += 1

        elif action_type == 'back':
            recorder.add_action('back', inferred=False)
            click.echo("✓ 添加操作: 返回")
            action_count += 1

        elif action_type == 'input' and len(parts) >= 2:
            text = ' '.join(parts[1:])
            recorder.add_action('input_text', text=text, inferred=False)
            click.echo(f"✓ 添加操作: 输入 '{text}'")
            action_count += 1

        elif action_type == 'swipe' and len(parts) >= 5:
            x1, y1, x2, y2 = map(int, parts[1:5])
            recorder.add_action('swipe', x1=x1, y1=y1, x2=x2, y2=y2, inferred=False)
            click.echo(f"✓ 添加操作: 滑动 ({x1}, {y1}) -> ({x2}, {y2})")
            action_count += 1

        else:
            click.echo(f"✗ 无法识别的操作: {action_input}")
            click.echo("提示: 使用格式 'click <文本>' 或 'back'")

    if action_count == 0:
        click.echo("\n没有记录任何操作")
        return

    filepath = recorder.stop()
    click.echo(f"\n✅ 录制完成: {filepath}")
    click.echo(f"📝 共记录 {action_count} 个操作")

    if not output:
        output = filepath.replace(".json", ".py")

    recorder.generate_code(filepath, output)
    click.echo(f"🚀 代码已生成: {output}")
    click.echo(f"执行: python {output}")


if __name__ == "__main__":
    cli()
