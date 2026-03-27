# 项目结构说明

## 目录结构

```
ai_mobile_control/
├── apps/                          # 应用模块（按平台划分）
│   └── douyin/
│       ├── client.py              # 基础客户端：设备连接、页面等待、导航、状态恢复
│       └── features/              # 功能模块（每个文件对应一个业务功能）
│           ├── __init__.py
│           ├── profile.py         # 个人主页：获取信息、粉丝列表、编辑简介
│           ├── feed.py            # 推荐视频流：扫描视频、采集评论
│           ├── live.py            # 直播间：主播信息、在线人数、弹幕（第一版）
│           └── live.md            # 直播间功能需求文档 & 待开发 TODO
│
├── core/                          # 设备控制核心层
│   ├── adb_manager.py             # ADB 封装：点击、滑动、按键、文本输入
│   ├── device_controller.py       # agent-device 封装：快照、元素点击
│   ├── executor.py                # AI 执行器：将 AI 决策转化为设备操作
│   └── recorder.py                # 操作录制器
│
├── ai_brain/                      # AI 决策层
│   ├── deepseek_client.py         # DeepSeek API 客户端：页面分析、执行规划
│   └── ai_agent.py                # AI 智能代理：大脑 + 执行器协同
│
├── cli/                           # 命令行接口
│   ├── main.py                    # 入口
│   ├── commands.py                # 所有 CLI 命令定义
│   └── ai_commands.py             # AI 相关命令
│
├── config/
│   └── settings.py                # 配置管理，读取 .env
│
├── examples/                      # 使用示例
├── output/                        # 运行输出（快照、扫描结果等）
├── logs/                          # 日志文件
├── recordings/                    # 操作录制文件
├── .env                           # 环境变量
├── requirements.txt
└── run.py                         # 程序入口
```

## 分层设计

```
CLI / Python API
      ↓
  features/          ← 业务逻辑层，每个功能独立一个文件
      ↓
  client.py          ← 基础设施层，只管导航和页面状态
      ↓
  core/              ← 设备控制层，封装 ADB 和 agent-device
      ↓
  ADB / agent-device ← 底层设备通信
```

## 添加新功能

在 `apps/douyin/features/` 下新建文件，注入 `DouyinClient`：

```python
# apps/douyin/features/search.py
from apps.douyin.client import DouyinClient

class SearchFeature:
    def __init__(self, client: DouyinClient):
        self.client = client

    def search(self, keyword: str):
        try:
            self.client.ensure_open()
            # 实现搜索逻辑
        finally:
            self.client.return_to_feed()  # 操作完回到推荐页
```

## 添加新平台

在 `apps/` 下新建目录，复用 `core/` 层：

```python
# apps/wechat/client.py
from core.device_controller import DeviceController
from core.adb_manager import ADBManager

class WeChatClient:
    def __init__(self, device_id=None):
        self.device = DeviceController(device_id)
        self.adb = ADBManager()
```
