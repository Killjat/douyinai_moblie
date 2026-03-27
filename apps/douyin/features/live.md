# 需求文档：直播间数据采集功能（LiveFeature）

## 简介

本文档描述抖音直播间数据采集功能（LiveFeature）的需求规划。

项目背景：本项目是基于 agent-device + ADB 的 Android 手机自动化控制工具，已有 `ProfileFeature`（个人主页采集）和 `FeedFeature`（推荐视频流采集）。`LiveFeature` 遵循相同的架构模式：接收 `DouyinClient` 实例，自行负责业务逻辑，操作完成后调用 `client.return_to_feed()` 回到推荐页。

**实现范围**：本文档第一期（基础信息 + 打赏榜单）为当前迭代目标，第二期和第三期作为 Roadmap 占位，待后续迭代实现。

---

## 词汇表

- **LiveFeature**：直播间数据采集功能模块，本文档描述的主体系统
- **DouyinClient**：抖音基础客户端，提供设备连接、页面等待、导航等基础设施
- **直播间页面**：用户进入某主播直播时所在的页面，包含主播信息和互动区域
- **推荐页**：抖音首页推荐视频流页面，是所有 feature 操作完成后的统一返回状态
- **LiveInfo**：第一期采集结果的数据结构，包含主播昵称、直播标题、在线人数、直播分类、打赏榜单
- **RankItem**：打赏榜单中单个用户的数据结构，包含排名、用户昵称、打赏贡献值
- **打赏榜单**：直播间内展示贡献值最高的观众排名，通常可通过点击"贡献榜"或"礼物榜"入口查看
- **节点快照（nodes）**：通过 `client.get_nodes()` 获取的当前页面 UI 节点列表，每个节点含 `label`、`identifier`、`ref`、`hittable` 等字段
- **在线人数**：直播间当前同时在线观看的用户数量，通常显示在直播间顶部

---

## 数据结构定义

### LiveInfo（第一期）

```python
@dataclass
class LiveInfo:
    anchor_name: str        # 主播昵称，如 "张三"
    title: str              # 直播标题，如 "今晚聊聊最新科技"
    viewer_count: str       # 在线人数原始文本，如 "1.2万" / "999"
    category: str           # 直播分类/标签，如 "游戏" / "生活"
    rank: List[RankItem]    # 打赏榜单，最多 10 条，按排名升序
    collected_at: str       # 采集时间，ISO 8601 格式
```

> 说明：`viewer_count` 保留原始文本（含"万"等单位），由调用方决定是否转换为数值，避免精度损失。

### RankItem（第一期）

```python
@dataclass
class RankItem:
    rank: int               # 排名，从 1 开始
    username: str           # 用户昵称
    contribution: str       # 贡献值原始文本，如 "12.3万" / "888"
```

> 说明：`contribution` 保留原始文本，与 `viewer_count` 保持一致的处理策略。

### DanmakuItem（第二期，占位）

```python
@dataclass
class DanmakuItem:
    user: str               # 发送弹幕的用户昵称
    content: str            # 弹幕内容
    timestamp: str          # 采集时间戳
```

### GiftItem（第二期，占位）

```python
@dataclass
class GiftItem:
    user: str               # 送礼用户昵称
    gift_name: str          # 礼物名称，如 "玫瑰"
    quantity: int           # 礼物数量
    timestamp: str          # 采集时间戳
```

### ProductItem（第三期，占位）

```python
@dataclass
class ProductItem:
    name: str               # 商品名称
    price: str              # 商品价格原始文本，如 "¥99.00"
    rank: int               # 在购物车列表中的排序位置
```

---

## 需求

### 需求 1：进入直播间

**用户故事**：作为开发者，我希望 LiveFeature 能够从推荐页进入指定直播间，以便后续采集直播间数据。

#### 验收标准

1. WHEN `LiveFeature.collect()` 被调用，THE `LiveFeature` SHALL 调用 `client.ensure_open()` 确认抖音处于前台
2. WHEN 当前页面不是直播间页面，THE `LiveFeature` SHALL 通过节点快照识别直播间入口并导航进入
3. IF 在 15 秒内未能识别到直播间页面特征节点，THEN THE `LiveFeature` SHALL 抛出 `TimeoutError` 并附带描述信息 `"等待直播间页面超时"`
4. THE `LiveFeature` SHALL 通过检测节点中包含在线人数相关标签来判断直播间页面已就绪

---

### 需求 2：采集直播间基础信息（第一期核心需求）

**用户故事**：作为数据分析师，我希望能采集直播间的主播昵称、直播标题、在线人数和直播分类，以便分析直播内容和受众规模。

#### 验收标准

1. WHEN 直播间页面就绪，THE `LiveFeature` SHALL 从节点快照中解析主播昵称并存入 `LiveInfo.anchor_name`
2. WHEN 直播间页面就绪，THE `LiveFeature` SHALL 从节点快照中解析直播标题并存入 `LiveInfo.title`
3. WHEN 直播间页面就绪，THE `LiveFeature` SHALL 从节点快照中解析在线人数文本并存入 `LiveInfo.viewer_count`
4. WHEN 直播间页面就绪，THE `LiveFeature` SHALL 从节点快照中解析直播分类或标签并存入 `LiveInfo.category`
5. IF 某字段在节点快照中未找到对应节点，THEN THE `LiveFeature` SHALL 将该字段设为空字符串 `""` 并通过 `logger.warning` 记录缺失字段名
6. THE `LiveFeature` SHALL 在 `LiveInfo.collected_at` 中记录采集时的 ISO 8601 格式时间戳
7. THE `LiveFeature.collect()` SHALL 返回一个 `LiveInfo` 实例

---

### 需求 5：采集打赏榜单（第一期）

**用户故事**：作为运营人员，我希望能采集直播间打赏榜单的前 10 名用户及其贡献值，以便了解核心粉丝的打赏情况和忠诚度。

#### 验收标准

1. WHEN 直播间页面就绪，THE `LiveFeature` SHALL 识别并点击贡献榜/礼物榜入口按钮，打开榜单面板
2. WHEN 榜单面板打开，THE `LiveFeature` SHALL 等待榜单内容节点出现（以排名数字或用户昵称节点为判断依据），超时时间 10 秒
3. WHEN 榜单面板就绪，THE `LiveFeature` SHALL 从节点快照中解析前 10 名用户数据，每条记录包含排名、用户昵称、贡献值
4. IF 榜单不足 10 名（如直播刚开始），THEN THE `LiveFeature` SHALL 采集实际存在的条目，`LiveInfo.rank` 长度可少于 10
5. IF 未找到榜单入口按钮，THEN THE `LiveFeature` SHALL 将 `LiveInfo.rank` 设为空列表 `[]` 并通过 `logger.warning` 记录
6. WHEN 榜单采集完成，THE `LiveFeature` SHALL 关闭榜单面板，回到直播间主页面
7. THE `LiveFeature` SHALL 将榜单数据存入 `LiveInfo.rank`，类型为 `List[RankItem]`，按排名升序排列

---

### 需求 3：操作完成后回到推荐页

**用户故事**：作为开发者，我希望 LiveFeature 操作完成后能自动回到推荐页，以便保持与其他 feature 一致的干净状态。

#### 验收标准

1. WHEN `collect()` 方法正常执行完毕，THE `LiveFeature` SHALL 调用 `client.return_to_feed()` 回到推荐页
2. IF `collect()` 方法执行过程中抛出异常，THEN THE `LiveFeature` SHALL 在 `finally` 块中调用 `client.return_to_feed()`，确保无论成功或失败都回到推荐页
3. IF `collect()` 方法执行失败，THEN THE `LiveFeature` SHALL 返回一个各字段均为空字符串的 `LiveInfo` 实例，而不是抛出异常给调用方

---

### 需求 4：错误处理与日志

**用户故事**：作为开发者，我希望 LiveFeature 有完善的错误处理和日志，以便排查采集失败的原因。

#### 验收标准

1. WHEN 采集成功，THE `LiveFeature` SHALL 通过 `logger.success` 输出包含主播昵称和在线人数的摘要日志
2. WHEN 节点解析过程中发生异常，THE `LiveFeature` SHALL 通过 `logger.error` 记录异常信息，并继续尝试解析其他字段
3. THE `LiveFeature` SHALL 使用 `loguru` 的 `logger` 进行所有日志输出，与项目其他模块保持一致

---

## Roadmap

### 第二期：动态数据采集（未来规划）

> 本期需求暂不实现，作为占位记录。

**目标**：在直播间停留一段时间，持续采集弹幕和礼物信息。

- 弹幕采集：周期性获取节点快照，识别新增弹幕节点，去重后追加到 `List[DanmakuItem]`
- 礼物采集：识别礼物动画/通知节点，解析送礼用户和礼物名称
- 采集时长：支持传入 `duration` 参数（秒），到时后停止采集并回到推荐页
- 数据结构：`DanmakuItem`、`GiftItem`（见上方数据结构定义）

---

### 第三期：带货数据采集（未来规划）

> 本期需求暂不实现，作为占位记录。

**目标**：采集直播间购物车中的商品信息。

- 商品列表：点击购物车入口，滚动列表，采集所有商品的名称和价格
- 数据结构：`ProductItem`（见上方数据结构定义）
- 注意事项：需处理购物车未开启的情况（非带货直播间）

---

## 实现状态

### 第一版已实现

| 字段 | 状态 | 解析方式 |
|------|------|---------|
| `anchor_name` | ✅ 已实现 | `identifier` 含 `user_name` 的节点 |
| `viewer_count` | ✅ 已实现 | `identifier` 以 `oke` 结尾的数字节点 |
| `danmaku` | ✅ 已实现 | `identifier` 含 `/text`，label 以 `\u200e*` 开头 |
| `title` | ❌ 待调研 | 见下方 TODO |
| `category` | ❌ 待调研 | 见下方 TODO |
| `rank` | ❌ 待调研 | 见下方 TODO |

---

## TODO：待调研项

### 1. 直播标题

**问题**：进入直播间时有"本场成员"弹窗遮挡，关闭弹窗后页面会退出直播间（小直播间行为）。需要在人气更高的直播间中，找到关闭弹窗后仍留在直播间的场景，观察标题节点的 `identifier` 或 `label` 规律。

**调研步骤**：
1. 进入一个在线人数 > 1000 的直播间
2. 不关弹窗，直接调用 `client.get_nodes()` 打印所有节点
3. 找到直播标题对应的节点 `identifier`

---

### 2. 直播分类/标签

**问题**：当前快照中未发现分类标签节点（如"游戏"、"生活"等）。可能在直播间顶部区域，被其他节点覆盖。

**调研步骤**：
1. 进入明确有分类标签的直播间（如游戏直播）
2. 打印完整节点，搜索分类关键词

---

### 3. 人气榜前10

**问题**：`'人气榜，按钮'` 节点 `hittable: False`，无法直接点击。原因是被"本场成员"弹窗遮挡。

**调研步骤**：
1. 进入直播间，不触发弹窗（或等弹窗自动消失）
2. 确认人气榜按钮变为 `hittable: True`
3. 点击后观察榜单面板节点结构，找排名、用户名、贡献值的 `identifier`

**预期节点格式**（待验证）：
```
排名数字节点 + 用户昵称节点 + 贡献值节点（相邻排列）
```

### 与现有 Feature 的对比

| 模块 | 入口导航 | 核心解析 | 返回推荐页 |
|------|----------|----------|------------|
| `ProfileFeature` | `client.navigate_to_profile()` | `_parse(nodes)` | `finally: client.return_to_feed()` |
| `FeedFeature` | `client.navigate_to_feed()` | `_parse_video(nodes)` | `client.return_to_feed()` |
| `LiveFeature` | 待实现 `_navigate_to_live()` | 待实现 `_parse(nodes)` | `finally: client.return_to_feed()` |

### 代码骨架

```python
"""
直播间数据采集功能模块（第一期：基础信息 + 打赏榜单）
- 采集主播昵称、直播标题、在线人数、直播分类
- 采集打赏榜单前 10 名（用户昵称 + 贡献值）
"""
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Any
from loguru import logger
from apps.douyin.client import DouyinClient


@dataclass
class RankItem:
    rank: int               # 排名，从 1 开始
    username: str           # 用户昵称
    contribution: str       # 贡献值原始文本，如 "12.3万"


@dataclass
class LiveInfo:
    anchor_name: str = ""
    title: str = ""
    viewer_count: str = ""
    category: str = ""
    rank: List[RankItem] = field(default_factory=list)  # 打赏榜单，最多 10 条
    collected_at: str = ""


class LiveFeature:
    """直播间数据采集功能"""

    def __init__(self, client: DouyinClient):
        self.client = client

    def collect(self) -> LiveInfo:
        """采集当前直播间基础信息 + 打赏榜单"""
        try:
            self.client.ensure_open()
            nodes = self._wait_for_live_page()
            info = self._parse(nodes)
            info.rank = self._fetch_rank()
            return info
        except Exception as e:
            logger.error(f"采集直播间信息失败: {e}")
            return LiveInfo()
        finally:
            self.client.return_to_feed()

    def _wait_for_live_page(self) -> List[Dict]:
        """等待直播间页面就绪，返回 nodes"""
        # TODO: 根据实际直播间节点特征实现
        raise NotImplementedError

    def _parse(self, nodes: List[Dict]) -> LiveInfo:
        """从节点快照解析直播间基础信息"""
        info = LiveInfo(collected_at=datetime.now(timezone.utc).isoformat())
        # TODO: 根据实际节点 label 规律实现解析逻辑
        logger.success(f"直播间采集完成: 主播={info.anchor_name}, 在线={info.viewer_count}")
        return info

    def _fetch_rank(self, top_n: int = 10) -> List[RankItem]:
        """点击贡献榜入口，采集前 top_n 名打赏数据，采集后关闭榜单面板"""
        # TODO: 识别榜单入口节点 → 点击 → 等待面板 → 解析 → 关闭
        raise NotImplementedError

    def _parse_rank(self, nodes: List[Dict], top_n: int = 10) -> List[RankItem]:
        """从榜单面板节点快照解析排名数据"""
        # TODO: 根据实际节点 label 规律实现解析逻辑
        raise NotImplementedError
```

> 实现时需先进入一个真实直播间，通过 `client.get_nodes()` 打印节点快照，观察各字段对应的 `label` 规律，再编写解析逻辑。这与 `ProfileFeature._parse()` 和 `FeedFeature._parse_video()` 的开发方式一致。
