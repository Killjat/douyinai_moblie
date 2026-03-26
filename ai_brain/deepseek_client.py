"""
DeepSeek AI 大脑 - 负责分析和决策
"""
import os
import json
from typing import Dict, List, Any, Optional
from loguru import logger

try:
    from config.settings import settings
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False


class DeepSeekBrain:
    """DeepSeek AI 大脑 - 智能分析和决策"""

    def __init__(self, api_key: Optional[str] = None):
        """初始化 DeepSeek 大脑

        Args:
            api_key: DeepSeek API Key,如果不提供则从环境变量或配置文件读取
        """
        # 优先使用传入的 api_key，然后从环境变量，最后从配置文件读取
        self.api_key = (
            api_key or
            os.getenv("DEEPSEEK_API_KEY") or
            (settings.DEEPSEEK_API_KEY if SETTINGS_AVAILABLE else None)
        )

        # 读取其他配置
        self.base_url = (
            (settings.DEEPSEEK_BASE_URL if SETTINGS_AVAILABLE else "https://api.deepseek.com")
        )
        self.model = (
            (settings.DEEPSEEK_MODEL if SETTINGS_AVAILABLE else "deepseek-chat")
        )

        if not self.api_key:
            logger.warning("未设置 DEEPSEEK_API_KEY,将使用模拟模式")
            self.use_mock = True
        else:
            self.use_mock = False
            logger.info("DeepSeek 大脑已初始化")

    def analyze_page(self, snapshot: Dict[str, Any], task_description: str) -> Dict[str, Any]:
        """分析当前页面状态并给出建议

        Args:
            snapshot: 当前屏幕快照
            task_description: 任务描述

        Returns:
            分析结果和建议
        """
        if self.use_mock:
            return self._mock_analyze_page(snapshot, task_description)

        # TODO: 集成实际的 DeepSeek API
        return self._call_deepseek_api(snapshot, task_description)

    def _mock_analyze_page(self, snapshot: Dict[str, Any], task_description: str) -> Dict[str, Any]:
        """模拟 AI 分析(用于演示)"""
        nodes = snapshot.get("nodes", [])

        # 基础分析
        analysis = {
            "page_type": "unknown",
            "current_state": "",
            "key_elements": [],
            "suggested_actions": [],
            "next_step": "",
            "confidence": 0.0
        }

        # 检测页面类型
        has_launcher = any("huawei.android.launcher" in n.get("identifier", "") for n in nodes)
        has_douyin = any("com.ss.android.ugc.aweme" in n.get("identifier", "") for n in nodes)

        if has_launcher:
            analysis["page_type"] = "desktop"
            analysis["current_state"] = "手机桌面"
            analysis["key_elements"] = ["桌面启动器", "应用图标"]
            analysis["suggested_actions"] = [
                {"action": "open_app", "target": "com.ss.android.ugc.aweme", "reason": "打开抖音"}
            ]
            analysis["next_step"] = "打开抖音应用"
            analysis["confidence"] = 0.95

        elif has_douyin:
            # 检测抖音内具体页面
            nav_items = []
            for node in nodes:
                label = node.get("label", "").strip()
                if label in ["首页", "朋友", "消息", "我"]:
                    nav_items.append(label)

            if "我" in nav_items:
                # 检查是否在个人主页
                has_profile = any(
                    "粉丝" in n.get("label", "") and "新关注" not in n.get("label", "")
                    for n in nodes
                )

                if has_profile:
                    analysis["page_type"] = "douyin_profile"
                    analysis["current_state"] = "抖音个人主页"
                    analysis["key_elements"] = nav_items + ["粉丝", "关注", "获赞"]
                    analysis["suggested_actions"] = [
                        {"action": "extract_info", "target": "profile", "reason": "提取个人主页信息"}
                    ]
                    analysis["next_step"] = "提取个人主页信息"
                    analysis["confidence"] = 0.9
                else:
                    analysis["page_type"] = "douyin_other"
                    analysis["current_state"] = f"抖音 - {task_description}相关页面"
                    analysis["key_elements"] = nav_items
                    analysis["suggested_actions"] = [
                        {"action": "click", "target": "我", "reason": "点击'我'进入个人主页"}
                    ]
                    analysis["next_step"] = "点击底部导航'我'按钮"
                    analysis["confidence"] = 0.85

        analysis["task_context"] = task_description
        return analysis

    def _call_deepseek_api(self, snapshot: Dict[str, Any], task_description: str) -> Dict[str, Any]:
        """调用 DeepSeek API 进行分析

        Args:
            snapshot: 屏幕快照
            task_description: 任务描述

        Returns:
            分析结果
        """
        # TODO: 实现实际的 API 调用
        import openai

        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        # 构建提示词
        prompt = f"""
你是一个移动应用自动化专家。根据以下屏幕快照信息,分析当前页面状态并给出最佳操作建议。

任务目标: {task_description}

屏幕快照信息:
{json.dumps(snapshot, ensure_ascii=False, indent=2)}

请返回 JSON 格式的分析结果:
{{
    "page_type": "页面类型(desktop/douyin_home/douyin_profile/douyin_other)",
    "current_state": "当前状态描述",
    "key_elements": ["关键元素列表"],
    "suggested_actions": [
        {{"action": "动作类型", "target": "目标", "reason": "原因"}}
    ],
    "next_step": "下一步应该做什么",
    "confidence": 0.0-1.0
}}
"""

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个移动应用自动化专家,擅长分析屏幕快照并给出操作建议。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            logger.info(f"AI 分析完成: {result['page_type']}")
            return result

        except Exception as e:
            logger.error(f"调用 DeepSeek API 失败: {e}")
            return self._mock_analyze_page(snapshot, task_description)

    def plan_execution(self, task_description: str, current_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """规划执行步骤

        Args:
            task_description: 任务描述
            current_analysis: 当前页面分析结果

        Returns:
            执行步骤列表
        """
        if self.use_mock:
            return self._mock_plan_execution(task_description, current_analysis)

        # TODO: 使用 DeepSeek API 规划
        return []

    def _mock_plan_execution(self, task_description: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """模拟执行规划"""
        steps = []

        if "获取个人主页" in task_description or "profile" in task_description.lower():
            if analysis["page_type"] == "desktop":
                steps.append({
                    "step": 1,
                    "action": "open_app",
                    "target": "com.ss.android.ugc.aweme",
                    "description": "打开抖音应用",
                    "wait": 2
                })
                steps.append({
                    "step": 2,
                    "action": "wait",
                    "duration": 2,
                    "description": "等待应用加载"
                })
                steps.append({
                    "step": 3,
                    "action": "click_by_text",
                    "target": "我",
                    "description": "点击'我'进入个人主页",
                    "wait": 2.5
                })
                steps.append({
                    "step": 4,
                    "action": "extract_profile_info",
                    "description": "提取个人主页信息"
                })

            elif analysis["page_type"] == "douyin_other":
                steps.append({
                    "step": 1,
                    "action": "click_by_text",
                    "target": "我",
                    "description": "点击'我'进入个人主页",
                    "wait": 2.5
                })
                steps.append({
                    "step": 2,
                    "action": "extract_profile_info",
                    "description": "提取个人主页信息"
                })

            elif analysis["page_type"] == "douyin_profile":
                steps.append({
                    "step": 1,
                    "action": "extract_profile_info",
                    "description": "提取个人主页信息"
                })

        steps.append({
            "step": len(steps) + 1,
            "action": "done",
            "description": "任务完成"
        })

        return steps

    def adjust_plan(self, current_step: Dict[str, Any], snapshot: Dict[str, Any], error: Optional[str] = None) -> Dict[str, Any]:
        """根据执行结果调整计划

        Args:
            current_step: 当前执行的步骤
            snapshot: 当前快照
            error: 错误信息(如果有)

        Returns:
            调整后的建议
        """
        if error:
            logger.warning(f"步骤执行出错: {error}")
            # 分析错误原因并给出建议
            return {
                "should_retry": True,
                "adjustment": "检查页面状态后重试",
                "suggested_action": "analyze_and_replan"
            }

        # 成功执行,继续下一步
        return {
            "should_retry": False,
            "adjustment": "继续执行下一步",
            "suggested_action": "next_step"
        }
