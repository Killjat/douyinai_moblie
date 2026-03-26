"""
AI 智能代理 - 大脑 + 手脚协同工作
"""
import json
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from loguru import logger

from ai_brain.deepseek_client import DeepSeekBrain
from core.executor import Executor


class AIAgent:
    """AI 智能代理 - 深度集成 AI 智能和执行能力"""

    def __init__(self, device_id: Optional[str] = None, deepseek_api_key: Optional[str] = None):
        """初始化 AI 代理

        Args:
            device_id: 设备 ID
            deepseek_api_key: DeepSeek API Key
        """
        self.brain = DeepSeekBrain(deepseek_api_key)
        self.executor = Executor(device_id)
        self.execution_log = []
        self.max_retries = 3
        self.max_steps = 20

    def execute_task(self, task_description: str, max_steps: int = 20) -> Dict[str, Any]:
        """执行任务 - AI 作为大脑,代码作为手脚

        Args:
            task_description: 任务描述
            max_steps: 最大步骤数

        Returns:
            执行结果
        """
        logger.info("=" * 70)
        logger.info(f"AI 智能代理启动")
        logger.info(f"任务: {task_description}")
        logger.info("=" * 70)

        self.max_steps = max_steps
        current_step = 0
        retry_count = 0

        while current_step < self.max_steps:
            current_step += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"第 {current_step} 步")
            logger.info(f"{'='*70}")

            # 1. 获取当前状态
            current_state = self.executor.get_current_state()
            logger.debug("已获取当前状态")

            # 2. AI 分析当前页面
            logger.info("AI 分析当前页面...")
            analysis = self.brain.analyze_page(
                current_state["snapshot"],
                task_description
            )

            logger.info(f"页面类型: {analysis['page_type']}")
            logger.info(f"当前状态: {analysis['current_state']}")
            logger.info(f"下一步: {analysis['next_step']}")
            logger.info(f"置信度: {analysis['confidence']}")

            # 3. 检查任务是否完成
            if self._is_task_complete(analysis, task_description):
                logger.success("🎉 任务完成!")
                break

            # 4. AI 规划执行步骤
            logger.info("AI 规划执行步骤...")
            if current_step == 1 or retry_count > 0:
                # 第一步或重试时重新规划
                plan = self.brain.plan_execution(task_description, analysis)
                logger.info(f"执行计划包含 {len(plan)} 个步骤")
                self.current_plan = plan
                self.current_plan_index = 0

            # 5. 执行当前步骤
            if self.current_plan_index >= len(self.current_plan):
                logger.warning("计划已执行完毕,重新分析...")
                retry_count += 1
                if retry_count >= self.max_retries:
                    logger.error("达到最大重试次数,停止执行")
                    break
                continue

            step = self.current_plan[self.current_plan_index]
            self.current_plan_index += 1

            # 6. 执行步骤
            execution_result = self.executor.execute_step(step)

            # 记录执行日志
            log_entry = {
                "step": current_step,
                "analysis": analysis,
                "action": step,
                "result": execution_result
            }
            self.execution_log.append(log_entry)

            # 7. AI 评估执行结果并调整
            if execution_result["success"]:
                logger.success(f"✓ 步骤执行成功")
                retry_count = 0  # 重置重试计数

                # 让 AI 评估是否需要调整
                adjustment = self.brain.adjust_plan(step, current_state["snapshot"])

                if not adjustment["should_retry"]:
                    continue

            else:
                logger.error(f"✗ 步骤执行失败: {execution_result.get('error')}")

                # AI 分析失败原因并调整
                adjustment = self.brain.adjust_plan(
                    step,
                    current_state["snapshot"],
                    execution_result.get("error")
                )

                retry_count += 1
                if retry_count >= self.max_retries:
                    logger.error("达到最大重试次数,停止执行")
                    break

                logger.info(f"AI 建议: {adjustment['adjustment']}")
                self.current_plan_index = 0  # 重新开始

            # 等待页面稳定
            time.sleep(1)

        # 返回结果
        final_state = self.executor.get_current_state()
        result = {
            "task": task_description,
            "completed": self._is_task_complete(analysis, task_description),
            "steps_executed": current_step,
            "execution_log": self.execution_log,
            "final_state": final_state
        }

        # 保存执行日志
        self._save_execution_log(result)

        return result

    def _is_task_complete(self, analysis: Dict[str, Any], task_description: str) -> bool:
        """判断任务是否完成

        Args:
            analysis: AI 分析结果
            task_description: 任务描述

        Returns:
            是否完成
        """
        # 根据任务类型判断
        if "个人主页" in task_description or "profile" in task_description.lower():
            # 检查是否在个人主页且已提取信息
            return analysis["page_type"] == "douyin_profile"

        elif "粉丝" in task_description or "followers" in task_description.lower():
            # 检查是否已获取粉丝信息
            # TODO: 根据实际执行结果判断
            return False

        return False

    def _save_execution_log(self, result: Dict[str, Any]):
        """保存执行日志

        Args:
            result: 执行结果
        """
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = Path("output") / f"execution_log_{timestamp}.json"

        log_file.parent.mkdir(parents=True, exist_ok=True)

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"执行日志已保存: {log_file}")

    def interactive_mode(self):
        """交互式模式 - 用户可以实时看到 AI 决策并干预"""
        logger.info("进入交互式模式...")
        logger.info("输入任务描述, AI 将自动分析和执行")
        logger.info("输入 'quit' 退出")

        while True:
            try:
                task = input("\n> 请输入任务: ").strip()

                if not task:
                    continue

                if task.lower() in ["quit", "exit", "q"]:
                    logger.info("退出交互式模式")
                    break

                # 执行任务
                result = self.execute_task(task)

                if result["completed"]:
                    logger.success(f"任务 '{task}' 已完成")
                else:
                    logger.warning(f"任务 '{task}' 未完成,请检查日志")

            except KeyboardInterrupt:
                logger.info("用户中断")
                break
            except Exception as e:
                logger.error(f"执行出错: {e}")


# 便捷函数
def create_agent(device_id: Optional[str] = None, api_key: Optional[str] = None) -> AIAgent:
    """创建 AI 代理

    Args:
        device_id: 设备 ID
        api_key: DeepSeek API Key

    Returns:
        AI 代理实例
    """
    return AIAgent(device_id, api_key)
