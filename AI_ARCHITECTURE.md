# AI 智能代理架构

## 核心理念

**AI 作为大脑，代码作为手脚**

- DeepSeek AI：负责分析页面状态、制定执行计划、处理异常
- Python 代码：负责执行具体的设备操作
- 协同方式：AI 分析 → 规划步骤 → 代码执行 → 反馈结果 → AI 调整

## 工作流程

```
用户输入任务
    ↓
AI 分析当前页面快照
    ↓
AI 规划执行步骤
    ↓
Executor 执行当前步骤
    ↓
获取执行结果
    ↓
AI 评估并调整计划
    ↓
循环直到任务完成
```

## 模块说明

### DeepSeekBrain（大脑）

`ai_brain/deepseek_client.py`

- `analyze_page(snapshot, task)` — 分析当前页面，识别页面类型和关键元素
- `plan_execution(task, analysis)` — 根据任务和页面状态规划执行步骤
- `adjust_plan(step, snapshot, error)` — 执行失败时分析原因并调整策略

未配置 API Key 时自动降级为规则模式（mock），不影响基础功能使用。

```python
from ai_brain.deepseek_client import DeepSeekBrain

brain = DeepSeekBrain(api_key="your-api-key")
analysis = brain.analyze_page(snapshot, "获取个人主页信息")
plan = brain.plan_execution("获取个人主页信息", analysis)
```

### Executor（手脚）

`core/executor.py`

将 AI 规划的步骤转化为实际设备操作：

- `open_app` — 打开应用
- `click_by_text` / `click_by_ref` — 点击元素
- `swipe` / `back` / `home` — 导航操作
- `extract_profile_info` — 提取页面数据

```python
from core.executor import Executor

executor = Executor()
result = executor.execute_step({
    "action": "click_by_text",
    "target": "我",
    "description": "点击底部导航'我'按钮"
})
```

### AIAgent（协调者）

`ai_brain/ai_agent.py`

协调大脑和手脚，管理执行循环、重试逻辑和日志记录。

```python
from ai_brain.ai_agent import create_agent

agent = create_agent()
result = agent.execute_task("获取抖音个人主页信息")
```

命令行使用：

```bash
python3 run.py ai execute "获取抖音个人主页信息"
python3 run.py ai interactive
python3 run.py ai analyze
```

## 与 features/ 的关系

`features/` 下的模块（ProfileFeature、FeedFeature 等）是确定性自动化，适合流程固定的任务。

AI Agent 适合流程不固定、需要动态决策的任务，两者可以结合使用：

| 场景 | 推荐方式 |
|------|---------|
| 获取个人主页信息 | ProfileFeature（确定性，速度快） |
| 扫描推荐视频 | FeedFeature（确定性，速度快） |
| 复杂多步骤任务 | AIAgent（动态规划，适应性强） |
| 页面结构变化后 | AIAgent（自动适应新布局） |

## 扩展方向

- 支持更多应用（微信、小红书等）
- 多设备并发控制
- 集成视觉识别处理图片类 UI
- 执行历史记录，优化决策策略
