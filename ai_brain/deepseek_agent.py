"""
DeepSeek 驱动的智能代理
- DeepSeek 作为大脑，通过 function calling 决策下一步
- ToolExecutor 作为手脚，执行具体操作
"""
import json
import os
from typing import Dict, Any, List, Optional
from loguru import logger
import openai

from ai_brain.tool_executor import ToolExecutor, TOOLS


SYSTEM_PROMPT = """你是一个抖音手机自动化助手，可以控制手机上的抖音 App 完成各种任务。

你有以下工具可以使用：
- get_screen_state: 查看当前屏幕状态
- navigate_to_feed: 回到推荐页
- search_keyword: 搜索关键词并采集视频/评论
- scan_feed: 扫描推荐视频流
- get_profile: 获取个人主页信息
- get_search_history: 查看搜索历史
- tap_screen: 点击屏幕坐标
- press_back: 按返回键
- finish: 任务完成，返回结果

工作原则：
1. 先用 get_screen_state 了解当前状态，再决定下一步
2. 优先使用高层工具（search_keyword、scan_feed），避免直接操作坐标
3. 遇到错误时，先 press_back 回到已知状态，再重试
4. 采集到足够数据后，调用 finish 结束任务
5. 每次工具调用后，根据返回结果决定下一步，不要盲目执行
"""


class DeepSeekAgent:
    """DeepSeek function calling 驱动的智能代理"""

    def __init__(self, device_id: Optional[str] = None, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        if not self.api_key:
            raise ValueError("未设置 DEEPSEEK_API_KEY")

        self.llm = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.executor = ToolExecutor(device_id)
        self.messages: List[Dict] = []

    def run(self, task: str, max_rounds: int = 20) -> Dict[str, Any]:
        """
        执行任务。DeepSeek 通过 function calling 循环决策，
        直到调用 finish 或达到最大轮次。
        """
        logger.info(f"任务开始: {task}")
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]

        for round_num in range(1, max_rounds + 1):
            logger.info(f"── 第 {round_num} 轮决策 ──")

            response = self.llm.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.1,
            )

            msg = response.choices[0].message
            self.messages.append(msg.model_dump(exclude_none=True))

            # 没有 tool call，DeepSeek 直接回复文字，任务结束
            if not msg.tool_calls:
                logger.info(f"DeepSeek 回复: {msg.content}")
                return {
                    "task": task,
                    "rounds": round_num,
                    "reply": msg.content,
                    "data": self.executor._collected_data,
                }

            # 执行所有 tool calls
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                tool_result = self.executor.execute(tool_name, arguments)

                # finish 工具：任务完成
                if tool_name == "finish":
                    logger.success(f"任务完成: {arguments.get('summary', '')}")
                    return {
                        "task": task,
                        "rounds": round_num,
                        "summary": arguments.get("summary", ""),
                        "data": tool_result.get("result", {}).get("data", self.executor._collected_data),
                    }

                # 把工具结果加入对话
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })

        logger.warning(f"达到最大轮次 {max_rounds}，强制结束")
        return {
            "task": task,
            "rounds": max_rounds,
            "data": self.executor._collected_data,
        }
