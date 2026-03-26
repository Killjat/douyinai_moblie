# AI Mobile Control - 手机自动化控制工具

基于 agent-device 的 Python 工程化实现,支持 Android/iOS 设备的自动化控制。

## 功能特性

- **设备管理**: 自动检测和连接设备
- **应用控制**: 打开、关闭应用
- **UI 自动化**: 基于可访问性树的元素查找和操作
- **抖音自动化**: 粉丝信息获取、个人主页编辑等
- **日志系统**: 详细的操作日志记录

## 项目结构

```
ai_moblie_control/
├── ai_mobile_control/           # 主包
│   └── __init__.py
├── apps/                       # 应用模块
│   └── douyin/                 # 抖音应用
│       ├── __init__.py
│       └── client.py           # 抖音客户端
├── cli/                        # 命令行接口
│   ├── __init__.py
│   ├── main.py                 # 主入口
│   └── commands.py             # CLI 命令
├── config/                     # 配置模块
│   ├── __init__.py
│   └── settings.py             # 配置文件
├── core/                       # 核心模块
│   ├── __init__.py
│   ├── adb_manager.py          # ADB 管理器
│   └── device_controller.py    # 设备控制器
├── examples/                   # 使用示例
│   ├── example_usage.py        # 示例代码
│   ├── test_profile.py         # 测试个人主页
│   └── test_click_and_profile.py  # 测试点击
├── output/                     # 输出目录
├── logs/                       # 日志目录
├── screenshots/                # 截图目录
├── requirements.txt            # Python 依赖
├── run.py                      # 运行入口
├── PROJECT_STRUCTURE.md         # 项目结构文档
└── README.md                   # 项目文档
```

## 安装

### 前置要求

1. Python 3.8+
2. Node.js 16+ (用于安装 agent-device)
3. Android SDK 或 iOS 开发环境
4. 已连接并开启 USB 调试的设备

### 安装步骤

1. 安装 agent-device:
```bash
npm install -g agent-device
```

2. 安装 Python 依赖:
```bash
pip install -r requirements.txt
```

3. 连接设备并开启 USB 调试 (Android) 或信任电脑 (iOS)

4. 验证设备连接:
```bash
python3 run.py check
```

## 使用方法

### 命令行工具

#### 1. 检查设备连接
```bash
python3 run.py check
```

#### 2. 打开抖音
```bash
python3 run.py open-douyin
```

#### 3. 获取粉丝信息
```bash
python3 run.py followers
```

输出到文件:
```bash
python3 run.py followers --output output/followers.json
```

#### 4. 获取个人主页信息
```bash
python3 run.py profile
```

#### 5. 编辑个人简介
```bash
python3 run.py edit-bio
```

使用自定义简介:
```bash
python3 run.py edit-bio --bio "这是我的自定义简介"
```

#### 6. 获取屏幕快照
```bash
python3 run.py snapshot
```

### Python API

```python
from apps.douyin.client import DouyinClient

# 创建客户端
client = DouyinClient()

# 打开抖音
client.open_douyin()

# 获取粉丝信息
count = client.get_follower_count()
print(f"粉丝: {count['followers']}, 关注: {count['following']}")

# 获取个人主页信息
info = client.get_profile_info()
print(info)

# 编辑简介
client.edit_profile_bio("新的简介内容")
```

### 核心模块

#### ADBManager

```python
from core.adb_manager import ADBManager

adb = ADBManager()
adb.tap(500, 500)              # 点击
adb.input_text("hello")        # 输入文本
adb.press_key("KEYCODE_HOME")  # 按键
adb.swipe(500, 2000, 500, 1000)  # 滑动
```

#### DeviceController

```python
from core.device_controller import DeviceController

device = DeviceController()
snapshot = device.get_snapshot()  # 获取快照
device.press("@e123")             # 点击元素
device.press_text("确定")         # 通过文本点击
element = device.find_element_by_text("粉丝")  # 查找元素
```

## 配置说明

配置文件位于 `config/settings.py`:

```python
class Settings:
    # CyberStroll 简介
    CYBERSTROLL_BIO = "CyberStroll 跨境电商 - 专注于为全球消费者提供优质商品和购物体验"

    # 超时配置
    SNAPSHOT_TIMEOUT = 10
    WAIT_TIMEOUT = 5
```

## 日志

日志文件保存在 `logs/` 目录,包含:
- 控制台输出: INFO 级别
- 文件日志: DEBUG 级别,自动轮转和清理

## 常见问题

### 1. 设备未连接

确保:
- 设备已通过 USB 连接
- Android 设备已开启 USB 调试
- iOS 设备已信任电脑

### 2. agent-device 命令失败

检查:
```bash
agent-device devices
```

确保设备列表中包含你的设备。

### 3. 中文输入问题

ADB 无法直接输入中文。需要使用特殊方法:
1. 使用英文简介 (完全自动化)
2. 安装 ADB Keyboard 输入法 (一次设置,后续自动化)

## 开发指南

### 添加新应用

在 `apps/` 目录下创建新的应用模块:

```python
# apps/myapp/client.py
from core.device_controller import DeviceController
from loguru import logger

class MyAppClient:
    def __init__(self, device_id=None):
        self.device = DeviceController(device_id)

    def do_something(self):
        # 实现你的自动化逻辑
        pass
```

### 添加新命令

在 `cli/commands.py` 中添加:

```python
@cli.command()
@click.option("--device", "-d", help="设备 ID")
def my_command(device):
    """我的命令描述"""
    client = DouyinClient(device)
    # 实现命令逻辑
```

## 注意事项

1. 确保手机已连接并开启 USB 调试
2. 确保 agent-device 已安装并配置好
3. 中文输入受 ADB 限制,需要特殊处理
4. 操作过程中请保持屏幕常亮

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request!
# douyinai_moblie
