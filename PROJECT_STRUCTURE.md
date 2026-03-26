# AI Mobile Control - Python 工程化项目

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
│   └── example_usage.py        # 示例代码
├── output/                     # 输出目录
│   └── (自动生成)
├── logs/                       # 日志目录
│   └── (自动生成)
├── screenshots/                # 截图目录
├── requirements.txt            # Python 依赖
├── run.py                      # 运行入口
└── README.md                   # 项目文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 检查设备连接

```bash
python run.py check
```

### 3. 打开抖音

```bash
python run.py open-douyin
```

### 4. 获取粉丝信息

```bash
python run.py followers
```

### 5. 获取个人主页信息

```bash
python run.py profile
```

### 6. 编辑个人简介

```bash
python run.py edit-bio
```

或指定自定义简介:

```bash
python run.py edit-bio --bio "这是我的自定义简介"
```

### 7. 获取屏幕快照

```bash
python run.py snapshot
```

## 使用 Python API

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

## 核心模块

### ADBManager

ADB 设备管理器，提供基础 ADB 操作:

```python
from core.adb_manager import ADBManager

adb = ADBManager()
adb.tap(500, 500)              # 点击
adb.input_text("hello")        # 输入文本
adb.press_key("KEYCODE_HOME")  # 按键
adb.swipe(500, 2000, 500, 1000)  # 滑动
```

### DeviceController

基于 agent-device 的设备控制器:

```python
from core.device_controller import DeviceController

device = DeviceController()
snapshot = device.get_snapshot()  # 获取快照
device.press("@e123")             # 点击元素
device.press_text("确定")         # 通过文本点击
element = device.find_element_by_text("粉丝")  # 查找元素
```

### DouyinClient

抖音自动化客户端:

```python
from apps.douyin.client import DouyinClient

client = DouyinClient()
client.open_douyin()              # 打开抖音
client.get_follower_count()       # 获取粉丝数
client.extract_followers_list()   # 提取粉丝列表
client.get_profile_info()         # 获取个人信息
client.edit_profile_bio("简介")   # 编辑简介
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

日志文件保存在 `logs/` 目录，包含:
- 控制台输出: INFO 级别
- 文件日志: DEBUG 级别，自动轮转和清理

## 注意事项

1. 确保手机已连接并开启 USB 调试
2. 确保 agent-device 已安装并配置好
3. 中文输入受 ADB 限制，需要特殊处理
