# AI Mobile Control - 手机自动化控制工具

基于 `agent-device` + `ADB` 的 Python 工程化实现，支持 Android 设备的自动化控制。当前专注于抖音平台，提供个人主页数据采集、推荐内容扫描等功能，架构设计支持快速扩展到更多应用。

---

## 功能特性

### 抖音搜索功能 (SearchFeature)

智能关键词搜索，支持多种搜索模式和筛选方式：

- **基础搜索**：输入关键词搜索相关视频
- **搜索历史**：优先使用历史记录快速搜索，提升效率
- **话题模式**：进入话题详情页，采集该话题下的作品
- **最新筛选**：按最新发布时间筛选内容
- **智能输入**：自动识别搜索输入页与搜索结果页，避免误操作

```bash
# 基础搜索（采集 10 个视频）
python3 run.py search "跨境电商"

# 搜索并保存到文件
python3 run.py search "跨境电商" --count 20 --output output/search.json

# 话题模式：进入话题详情页采集
python3 run.py search "跨境电商" --topic

# 按最新发布筛选
python3 run.py search "跨境电商" --latest

# 查看搜索历史记录
python3 run.py search-history
```

```json
[
  {
    "nickname": "跨境电商达人",
    "author_handle": "@跨境电商达人",
    "title": "2025跨境电商发展趋势分析",
    "likes": "3.2万",
    "comment_count": "856",
    "shares": "234",
    "url": "https://v.douyin.com/xxx",
    "search_keyword": "跨境电商",
    "comments": [
      {
        "user": "用户A",
        "content": "很有用的分享",
        "total_in_video": "856条评论"
      }
    ]
  }
]
```

### 抖音个人主页 (ProfileFeature)

自动导航到抖音个人主页，提取账号的完整数据：

- 账号昵称
- 粉丝数 / 关注数 / 获赞数
- 粉丝列表
- 编辑个人简介

```bash
python3 run.py profile
```

```json
{
  "name": "cyberstroll跨境电商",
  "bio": "",
  "followers": 2,
  "following": 11,
  "likes": 0
}
```

### 抖音推荐视频扫描 (FeedFeature)

自动刷取推荐视频流，逐条采集每个视频的结构化数据：

- 作者昵称 / @ 句柄
- 视频标题 / 描述
- 点赞数 / 评论数 / 分享数 / 背景音乐
- 评论区内容（用户名 + 评论文本）

```bash
# 扫描 5 个视频（默认）
python3 run.py scan-feed

# 扫描 10 个并保存到文件
python3 run.py scan-feed --count 10 --output output/feed.json
```

```json
[
  {
    "author": "方明泉摄影",
    "author_handle": "@方明泉摄影",
    "title": "西大街30年巨变...",
    "likes": "524",
    "comment_count": "156",
    "shares": "26",
    "music": "@方明泉摄影创作的原声",
    "comments": [
      {
        "user": "小薛哥哥",
        "content": "90年的。招工进入北门清管所工作过3个多月...",
        "total_in_video": "156条评论"
      }
    ]
  }
]
```

### 抖音直播间采集 (LiveFeature)

进入直播间后，采集当前直播的完整数据：

- 主播昵称
- 本场点赞数
- 当前在线人数
- 在线观众列表（右上角前3名）
- 实时弹幕（用户名 + 内容）
- 礼物通知（自动从弹幕流中识别）

> 使用前需先在手机上进入直播间，然后运行命令。

```bash
python3 run.py live
python3 run.py live --output output/live.json
```

```json
{
  "anchor_name": "Sophia123",
  "total_likes": "123275",
  "viewer_count": "17",
  "top_viewers": [". Y", "动情✘", "自然醒"],
  "danmaku": [
    { "user": "冰美式🧊", "content": "哼，划就划", "is_gift": false },
    { "user": "七月🎊", "content": "@扫地僧 那你直接过", "is_gift": false }
  ],
  "gifts": [
    { "user": "李永恩✨✨", "content": "送了玫瑰 x1", "is_gift": true }
  ],
  "title": "",
  "category": "",
  "collected_at": "2026-03-27T08:38:06Z"
}
```

> `title`、`category` 待实现，详见 `apps/douyin/features/live.md`。

### 其他功能

- 设备管理：自动检测和连接 Android 设备
- 操作录制 / 回放：录制手机操作并生成可执行 Python 代码
- AI 智能代理：接入 DeepSeek，通过自然语言描述任务自动执行
- 日志系统：完整的操作日志记录

---

## 项目结构

```
ai_mobile_control/
├── apps/
│   └── douyin/
│       ├── client.py          # 基础设施：设备连接、页面等待、导航
│       └── features/
│           ├── profile.py     # 个人主页功能
│           ├── feed.py        # 推荐视频流功能
│           ├── search.py      # 搜索功能（支持历史记录、话题、最新筛选）
│           ├── live.py        # 直播间采集功能
│           └── live.md        # 直播间需求文档 & TODO
├── core/
│   ├── adb_manager.py         # ADB 管理器
│   ├── device_controller.py   # agent-device 控制器
│   └── executor.py            # AI 执行器
├── ai_brain/
│   ├── deepseek_client.py     # DeepSeek AI 客户端
│   └── ai_agent.py            # AI 智能代理
├── cli/
│   ├── commands.py            # CLI 命令
│   └── ai_commands.py         # AI 相关命令
├── config/
│   └── settings.py            # 配置文件
├── .env                       # 环境变量（API Key 等）
└── run.py                     # 入口
```

---

## 安装

### 前置要求

- Python 3.8+
- Node.js 16+
- Android 设备，已开启 USB 调试

### 步骤

```bash
# 1. 安装 agent-device
npm install -g agent-device

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 配置环境变量（可选，用于 AI 功能）
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 4. 验证设备连接
python3 run.py check
```

---

## 使用方法

### CLI 命令

```bash
# 检查设备连接
python3 run.py check

# 打开抖音
python3 run.py open-douyin

# 搜索功能
python3 run.py search "跨境电商"
python3 run.py search "跨境电商" --count 20 --output output/search.json
python3 run.py search "跨境电商" --topic --latest
python3 run.py search-history

# 获取个人主页信息
python3 run.py profile

# 获取粉丝信息
python3 run.py followers
python3 run.py followers --output output/followers.json

# 编辑个人简介
python3 run.py edit-bio --bio "新的简介内容"

# 扫描推荐视频流
python3 run.py scan-feed --count 5
python3 run.py scan-feed --count 10 --output output/feed.json

# 直播间采集（需先在手机上进入直播间）
python3 run.py live
python3 run.py live --output output/live.json

# AI 智能模式
python3 run.py ai execute "获取抖音个人主页信息"
python3 run.py ai interactive
```

### Python API

```python
from apps.douyin.client import DouyinClient
from apps.douyin.features import ProfileFeature, FeedFeature, SearchFeature

client = DouyinClient()

# 搜索功能
search = SearchFeature(client)
results = search.search("跨境电商", count=20, latest=True)
history = search.get_search_history()

# 个人主页
profile = ProfileFeature(client)
info = profile.get_info()
followers = profile.get_followers_list()
profile.edit_bio("新的简介")

# 推荐视频流
feed = FeedFeature(client)
videos = feed.scan(count=10)

# 直播间（需先在手机上进入直播间）
from apps.douyin.features import LiveFeature
live = LiveFeature(client)
info = live.collect()
```

---

## 架构设计

`DouyinClient` 只负责基础设施（设备连接、页面等待、导航、操作后回到推荐页），业务逻辑全部在 `features/` 下按功能模块拆分。新增功能只需在 `features/` 下添加新文件，注入 `client` 即可。

```python
# 添加新功能示例：apps/douyin/features/search.py
from apps.douyin.client import DouyinClient

class SearchFeature:
    def __init__(self, client: DouyinClient):
        self.client = client

    def search(self, keyword: str):
        self.client.ensure_open()
        # 实现搜索逻辑...
        self.client.return_to_feed()
```

---

## 配置

`config/settings.py` 和 `.env`：

```env
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

---

## 常见问题

**设备未连接**：确认 USB 调试已开启，手机上点击"允许 USB 调试"授权。

**agent-device 命令失败**：运行 `agent-device devices` 确认设备在列表中。

**中文输入问题**：ADB 不支持直接输入中文，需安装 ADB Keyboard 输入法。

---

## 开发计划

- [x] 搜索功能（基础搜索、历史记录、话题模式、最新筛选）
- [ ] 私信功能
- [x] 直播间采集（主播昵称、本场点赞、在线人数、观众列表、弹幕、礼物通知）
- [ ] 直播间标题 / 分类（调研中，见 `apps/douyin/features/live.md`）
- [ ] 多设备并发控制
- [ ] 更多平台支持（微信、小红书等）

---

## License

MIT
