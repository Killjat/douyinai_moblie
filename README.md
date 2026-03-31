# CyberHarvest - 抖音数据采集工具

基于 `agent-device` + `ADB` 的 Android 手机自动化采集工具，专注于抖音平台。提供桌面应用（Mac）和 CLI 两种使用方式，支持视频数据采集、实时结果展示、API 调用和 Neo4j 图谱写入。

---

## 桌面应用（CyberHarvest.app）

### 下载安装

下载 `CyberHarvest-1.0.0.dmg`，双击挂载后将 `CyberHarvest.app` 拖入 Applications 文件夹。

### 功能

- **搜索采集**：输入关键词，实时展示每条采集结果
- **先选后采**：快速扫描列表，勾选感兴趣的视频再采集
- **最新筛选**：按最新发布时间筛选
- **搜索历史**：右侧面板展示历史搜索记录，点击可加载结果
- **导出**：支持下载 JSON / TXT
- **API 调用**：每次搜索生成唯一 `search_id`，可通过 API 获取结果
- **系统检测**：自动检测 ADB、agent-device、ADBKeyboard 等依赖，支持一键安装

### API 使用

每次搜索完成后，界面会展示调用示例：

```bash
# 获取搜索结果
curl "http://127.0.0.1:18765/api/search/result/{search_id}"

# 查看搜索历史
curl "http://127.0.0.1:18765/api/search/history"
```

```python
import requests
resp = requests.get("http://127.0.0.1:18765/api/search/result/{search_id}")
data = resp.json()
for item in data['results']:
    print(item['nickname'], item['title'])
```

---

## CLI 使用

### 前置要求

- Python 3.8+
- Node.js 16+
- Android 设备，已开启 USB 调试
- ADBKeyboard 输入法（用于中文输入）

### 安装

```bash
# 1. 安装 agent-device
npm install -g agent-device

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY（可选）

# 4. 验证设备连接
python3 run.py check
```

### 搜索命令

```bash
# 基础搜索
python3 run.py search "跨境电商"

# 指定数量 + 保存文件
python3 run.py search "跨境电商" --count 20 --output output/search.json

# 按最新发布筛选
python3 run.py search "跨境电商" --latest

# 进入话题详情页采集
python3 run.py search "跨境电商" --topic

# 限制评论数量
python3 run.py search "跨境电商" --max-comments 10

# 获取视频链接（每条额外耗时约5秒）
python3 run.py search "跨境电商" --fetch-url

# 不写入 Neo4j
python3 run.py search "跨境电商" --no-neo4j
```

### 其他命令

```bash
python3 run.py profile          # 获取个人主页信息
python3 run.py scan-feed        # 扫描推荐视频流
python3 run.py live             # 采集直播间数据
python3 run.py followers        # 获取粉丝列表
python3 run.py check            # 检查设备连接
```

---

## 采集字段

每条视频包含以下字段：

| 字段 | 说明 |
|------|------|
| `nickname` | 作者昵称 |
| `author_handle` | @handle |
| `title` | 视频标题/描述 |
| `likes` | 点赞数 |
| `comment_count` | 评论总数 |
| `shares` | 分享数 |
| `date` | 发布日期 |
| `music` | 背景音乐 |
| `cover` | 封面截图路径 |
| `comments` | 评论列表 |
| `url` | 视频链接（需 `--fetch-url`）|
| `search_keyword` | 搜索关键词 |

---

## 项目结构

```
├── apps/douyin/
│   ├── client.py              # 设备连接、页面导航
│   ├── features/
│   │   ├── search.py          # 搜索功能
│   │   ├── feed.py            # 推荐视频流
│   │   ├── live.py            # 直播间采集
│   │   └── collectors/        # 采集器模块
│   │       ├── base.py        # 基类
│   │       ├── video.py       # 视频采集器
│   │       ├── image.py       # 图文采集器（待实现）
│   │       └── product.py     # 商品采集器（待实现）
│   └── neo4j_exporter.py      # Neo4j 写入
├── cyberharvest/
│   ├── backend/               # FastAPI 后端
│   │   ├── main.py
│   │   └── routers/
│   │       ├── search.py      # 搜索接口（SSE 实时推送）
│   │       └── system.py      # 依赖检测接口
│   └── frontend/              # Electron + React
│       ├── electron/          # Electron 主进程
│       └── src/               # React 前端
├── core/                      # ADB 设备控制层
├── config/settings.py         # 配置管理
└── run.py                     # CLI 入口
```

---

## Neo4j 数据结构

搜索结果自动写入 Neo4j，Work 节点包含：

```cypher
// 按 IP 统计使用次数
MATCH (w:Work) WHERE w.public_ip <> ''
RETURN w.public_ip, count(w) as cnt ORDER BY cnt DESC

// 热门关键词
MATCH (w:Work)
RETURN w.search_keyword, count(w) as cnt ORDER BY cnt DESC
```

---

## 配置

`.env` 文件：

```env
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
NEO4J_URI=bolt://your-host:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

---

## License

MIT
