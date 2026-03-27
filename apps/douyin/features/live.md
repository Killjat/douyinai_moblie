# 需求文档：直播间数据采集功能（LiveFeature）

## 简介

基于 agent-device + ADB 的抖音直播间数据采集模块。遵循项目统一架构：接收 `DouyinClient` 实例，操作完成后调用 `client.return_to_feed()` 回到推荐页。

---

## 数据结构

```python
@dataclass
class DanmakuItem:
    user: str       # 用户昵称
    content: str    # 弹幕内容

@dataclass
class LiveInfo:
    anchor_name: str = ""   # 主播昵称
    title: str = ""         # 直播标题
    viewer_count: str = ""  # 在线人数
    category: str = ""      # 直播分类/地区
    danmaku: List[DanmakuItem] = ...  # 当前可见弹幕
    collected_at: str = ""  # 采集时间 ISO 8601
```

---

## 实现状态

| 字段 | 状态 | 解析方式 |
|------|------|---------|
| `anchor_name` | ✅ 已实现 | 直播间内，`identifier` 含 `user_name` |
| `viewer_count` | ✅ 已实现 | 直播间内，`identifier` 以 `oke` 结尾 |
| `danmaku` | ✅ 已实现 | 直播间内，`identifier` 含 `/text`，label 以 `\u200e*` 开头 |
| `title` | ❌ 待调研 | 见 TODO #1 |
| `category` | ❌ 待调研 | 见 TODO #1 |

---

## TODO

### #1 直播标题 / 分类

**发现**：`title`（如"新人主播"）和 `category`（如"常州"）的节点只出现在**直播列表页的预览卡片**上（`resource-id: xma` / `pon`），进入直播间后这些节点消失。

**两种实现思路**：

方案 A：在进入直播间前，从列表页预览卡片采集标题和分类，再进入直播间采集其他数据。需要重构 `collect()` 的调用方式，由调用方先导航到列表页。

方案 B：进入直播间后，点击主播头像或名字，查看是否有详情页包含标题和分类节点。

**调研步骤**：
1. 停留在直播列表页，dump UI 树确认 `xma`/`pon` 节点的完整路径
2. 尝试方案 B：进入直播间后点击主播名字，观察弹出页面的节点

---

## TODO

### 打赏榜单

**状态**：❌ 技术限制，暂无法实现

**问题**：直播间右上角在线人数可点击，点击后弹出打赏榜单面板。但该面板为 WebView 渲染，`agent-device` 的 accessibility tree 无法获取面板内的用户名和贡献值节点（dump 后只有空容器节点）。

**可能的替代方案**（待评估）：
- 截图 + OCR 识别榜单内容
- 使用 ADB 的 `uiautomator` 配合 WebView 调试模式

---

## Roadmap

### 第二期：动态弹幕采集

当前只采集进入时可见的弹幕快照。后续支持：
- 传入 `duration` 参数持续采集指定秒数
- 周期性快照去重，追加新弹幕到列表

### 第三期：带货数据

- 点击购物车入口，采集商品名称和价格
- 需处理非带货直播间（购物车不存在）的情况
