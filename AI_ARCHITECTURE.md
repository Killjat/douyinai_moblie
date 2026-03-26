# AI 智能代理架构文档

## 🧠 架构设计

### 核心理念
**AI 作为大脑,代码作为手脚**

- **DeepSeek AI (大脑)**: 负责分析、决策、规划
- **Python 代码 (手脚)**: 负责执行具体的设备操作
- **协同工作**: AI 分析页面状态 → 制定执行计划 → 代码执行 → 反馈结果 → AI 调整

## 📁 项目结构

```
ai_moblie_control/
├── ai_brain/                   # AI 大脑模块
│   ├── __init__.py
│   ├── deepseek_client.py       # DeepSeek AI 客户端(大脑)
│   └── ai_agent.py             # AI 智能代理(大脑+手脚协同)
├── core/
│   ├── executor.py              # 手脚执行器
│   ├── device_controller.py     # 设备控制器
│   └── adb_manager.py         # ADB 管理器
├── cli/
│   ├── commands.py            # 传统命令
│   └── ai_commands.py        # AI 智能命令
└── examples/
    └── test_ai_agent.py       # AI 代理测试
```

## 🔄 工作流程

```
1. 用户输入任务
   ↓
2. AI 分析当前页面状态
   ↓
3. AI 规划执行步骤
   ↓
4. 手脚执行器执行当前步骤
   ↓
5. 获取执行结果
   ↓
6. AI 评估结果并调整计划
   ↓
7. 返回步骤 4 (循环直到任务完成或达到限制)
```

## 🧠 DeepSeek AI (大脑)

### 功能
1. **页面分析**
   - 识别当前页面类型(桌面、抖音首页、个人主页等)
   - 提取关键元素(按钮、文本、统计数据)
   - 给出操作建议

2. **执行规划**
   - 根据任务和当前状态制定执行计划
   - 拆分为具体的可执行步骤
   - 设置步骤优先级和依赖关系

3. **智能调整**
   - 分析执行失败的原因
   - 提出调整建议
   - 重新规划执行方案

### API 集成
```python
from ai_brain.deepseek_client import DeepSeekBrain

# 初始化 AI 大脑
brain = DeepSeekBrain(api_key="your-api-key")

# 分析页面
analysis = brain.analyze_page(snapshot, "获取个人主页")

# 规划执行
plan = brain.plan_execution(task, analysis)

# 调整计划
adjustment = brain.adjust_plan(step, snapshot, error)
```

## 👐 手脚执行器

### 功能
1. **应用操作**
   - 打开/关闭应用
   - 点击元素(通过文本或 ref)
   - 等待和滑动

2. **信息提取**
   - 从快照中提取用户信息
   - 统计数据提取
   - 结构化数据输出

3. **状态感知**
   - 获取当前页面快照
   - 识别页面元素
   - 判断操作结果

### API 使用
```python
from core.executor import Executor

executor = Executor()

# 执行步骤
result = executor.execute_step({
    "step": 1,
    "action": "click_by_text",
    "target": "我",
    "description": "点击'我'按钮"
})

# 获取当前状态
state = executor.get_current_state()
```

## 🤖 AI 智能代理

### 核心特性
1. **自主决策**: AI 自动分析并决定下一步操作
2. **错误恢复**: 执行失败时 AI 自动分析原因并调整策略
3. **智能重试**: 根据错误类型智能决定是否重试
4. **状态追踪**: 记录完整执行日志供后续分析

### 使用方式

#### 方式1: 直接调用
```python
from ai_brain.ai_agent import create_agent

agent = create_agent()
result = agent.execute_task("获取抖音个人主页信息")

if result["completed"]:
    print("任务完成!")
```

#### 方式2: 命令行
```bash
# 执行任务
python3 run.py ai execute "获取抖音个人主页信息"

# 交互式模式
python3 run.py ai interactive

# 分析当前页面
python3 run.py ai analyze
```

## 📋 支持的任务类型

1. **获取个人主页信息**
   - 自动导航到个人主页
   - 提取昵称、简介、粉丝数、关注数、获赞数

2. **获取粉丝列表**
   - 自动进入粉丝页面
   - 提取粉丝列表信息

3. **编辑个人简介**
   - 自动导航到编辑页面
   - 输入新的简介内容

4. **自定义任务**
   - 通过自然语言描述任务
   - AI 自动理解和规划

## 🎯 核心优势

### 与传统自动化的区别

| 特性 | 传统自动化 | AI 智能代理 |
|------|----------|-------------|
| 决策逻辑 | 硬编码 | AI 动态分析 |
| 错误处理 | 固定逻辑 | 智能诊断 |
| 页面变化 | 需要重新编码 | 自动适应 |
| 复杂任务 | 需要拆分 | 自动规划 |
| 可维护性 | 代码复杂 | 逻辑清晰 |

### 智能化体现

1. **页面感知**: 自动识别当前页面,不在错误的页面上盲目操作
2. **上下文理解**: 根据任务上下文理解最佳操作路径
3. **动态规划**: 根据实际情况动态调整执行计划
4. **经验学习**: (未来可扩展)记录执行历史,优化决策

## 🚀 扩展方向

### 1. 集成真实 DeepSeek API
当前使用模拟模式,可集成真实 API:
```python
# 设置 API Key
export DEEPSEEK_API_KEY="your-api-key"

# 或在代码中指定
agent = create_agent(api_key="your-api-key")
```

### 2. 支持更多应用
- 微信、支付宝等应用自动化
- 跨应用任务链

### 3. 多设备协同
- 同时控制多个设备
- 设备间数据同步

### 4. 视觉理解
- 集成图像识别
- 处理更复杂的 UI 元素

## 📝 开发指南

### 添加新的 AI 能力
1. 在 `deepseek_client.py` 中添加分析方法
2. 在 `executor.py` 中添加执行能力
3. 在 `ai_agent.py` 中集成

### 添加新的应用支持
1. 创建新的客户端模块
2. 实现页面分析方法
3. 注册到 AI 大脑

## 🔒 安全性

- API Key 通过环境变量管理
- 执行日志完整记录
- 敏感数据脱敏处理

## 📊 性能优化

- 快照缓存机制
- 异步执行支持
- 批量操作优化

## 🎓 学习资源

- [DeepSeek API 文档](https://platform.deepseek.com/docs)
- [agent-device 文档](https://github.com/callstackincubator/agent-device)
- 项目代码示例
