# AI 智能代理 - 使用指南

## 🎯 快速开始

### 1. AI 智能执行任务

```bash
# 直接让 AI 自动完成复杂任务
python3 run.py ai execute "获取抖音个人主页信息"

# 或使用 Python 代码
python3 examples/test_ai_agent.py
```

### 2. AI 分析当前页面

```bash
# 让 AI 分析并告诉你该做什么
python3 run.py ai analyze
```

### 3. 交互式 AI 助手

```bash
# 持续对话,让 AI 帮你完成任务
python3 run.py ai interactive

> 请输入任务: 打开抖音
[AI] 检测到桌面,正在打开抖音...
[AI] 抖音已打开

> 请输入任务: 获取粉丝列表
[AI] 已在抖音,导航到个人主页...
[AI] 正在提取粉丝信息...
[AI] 完成!获取到 10 个粉丝
```

## 🧠 AI 如何工作

### 传统方式 (傻傻的)
```python
# 不管当前在哪,硬编码操作
click("我")  # 如果不在抖音,这就错了!
extract_profile()
```

### AI 智能方式
```python
# 1. AI 分析当前页面 → "你在桌面"
# 2. AI 规划 → "先打开抖音,再点击'我'"
# 3. 代码执行 → 完美完成
agent.execute_task("获取个人主页")
```

## 🔧 配置 DeepSeek API

### 方式1: 环境变量(推荐)
```bash
export DEEPSEEK_API_KEY="your-api-key-here"
```

### 方式2: 代码中指定
```python
from ai_brain.ai_agent import create_agent

agent = create_agent(api_key="your-api-key-here")
```

## 📝 支持的任务

- ✅ 获取个人主页信息
- ✅ 获取粉丝列表
- ✅ 编辑个人简介
- ✅ 自然语言描述的任何任务

## 🎉 核心优势

1. **不傻了** - AI 会先看你在哪页,再决定怎么操作
2. **自动适应** - 页面变化了?AI 自动识别并调整
3. **智能重试** - 失败了?AI 分析原因后重新规划
4. **自然交互** - 用人话描述任务,不需要懂代码

## 📚 详细文档

查看 `AI_ARCHITECTURE.md` 了解完整的架构设计。
