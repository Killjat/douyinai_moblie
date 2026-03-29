"""
工具执行层 - 将现有控件封装为 DeepSeek function calling 可调用的工具
"""
import json
import time
from typing import Dict, Any, List, Optional
from loguru import logger
from apps.douyin.client import DouyinClient


# ── 工具定义（OpenAI function calling 格式）────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_screen_state",
            "description": "获取当前手机屏幕的页面状态和可见元素，用于了解当前在哪个页面",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate_to_feed",
            "description": "导航到抖音推荐视频流（首页）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_keyword",
            "description": "在抖音搜索关键词，采集相关视频和评论",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "count": {"type": "integer", "description": "采集视频数量，默认 5", "default": 5},
                    "max_comments": {"type": "integer", "description": "每个视频最多采集评论数，默认 10", "default": 10},
                    "topic": {"type": "boolean", "description": "是否进入话题页采集，默认 false", "default": False},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_feed",
            "description": "扫描推荐视频流，采集视频信息和评论",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "采集视频数量，默认 5", "default": 5},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_profile",
            "description": "获取当前账号的个人主页信息（昵称、粉丝数、关注数等）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_search_history",
            "description": "获取抖音搜索历史记录列表",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot_and_tap",
            "description": (
                "截取当前屏幕截图，描述你想点击的元素，由 AI 视觉分析决定坐标后点击。"
                "适用于 uiautomator 无法捕捉的 overlay/弹窗（如筛选面板）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "描述要点击的元素，例如'最新发布按钮'、'一天内选项'、'完成按钮'"
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tap_screen",
            "description": "点击屏幕指定坐标",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X 坐标"},
                    "y": {"type": "integer", "description": "Y 坐标"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_back",
            "description": "按返回键",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "任务完成，返回最终结果",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "任务完成摘要"},
                    "data": {"type": "object", "description": "采集到的数据"},
                },
                "required": ["summary"],
            },
        },
    },
]


class ToolExecutor:
    """工具执行器 - 接收 DeepSeek 的 function call，调用对应的控件"""

    def __init__(self, device_id: Optional[str] = None):
        self.client = DouyinClient(device_id)
        self._collected_data: Dict[str, Any] = {}

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具调用，返回结果"""
        logger.info(f"执行工具: {tool_name}({json.dumps(arguments, ensure_ascii=False)})")
        try:
            result = self._dispatch(tool_name, arguments)
            logger.info(f"工具结果: {str(result)[:200]}")
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return {"success": False, "error": str(e)}

    def _dispatch(self, tool_name: str, args: Dict[str, Any]) -> Any:
        from apps.douyin.features import SearchFeature, FeedFeature, ProfileFeature

        if tool_name == "get_screen_state":
            nodes = self.client.get_nodes()
            from apps.douyin.features.search import SearchFeature as SF
            # 用 _detect_page 感知状态
            labels = [n.get("label", "").strip() for n in nodes if n.get("label", "").strip()]
            return {
                "node_count": len(nodes),
                "visible_labels": labels[:30],
                "page_hint": self._guess_page(labels),
            }

        elif tool_name == "navigate_to_feed":
            self.client.ensure_at_feed()
            return "已导航到推荐页"

        elif tool_name == "search_keyword":
            keyword = args["keyword"]
            count = args.get("count", 5)
            max_comments = args.get("max_comments", 10)
            topic = args.get("topic", False)
            results = SearchFeature(self.client).search(
                keyword, count=count, topic=topic, max_comments=max_comments
            )
            self._collected_data.setdefault("search_results", []).extend(results)
            return {
                "keyword": keyword,
                "collected": len(results),
                "items": [
                    {
                        "title": r.get("title", "")[:50],
                        "nickname": r.get("nickname", ""),
                        "likes": r.get("likes", ""),
                        "comment_count": r.get("comment_count", ""),
                        "comments_collected": len(r.get("comments", [])),
                    }
                    for r in results
                ],
            }

        elif tool_name == "scan_feed":
            count = args.get("count", 5)
            results = FeedFeature(self.client).scan(count=count)
            self._collected_data.setdefault("feed_results", []).extend(results)
            return {"collected": len(results), "items": results}

        elif tool_name == "get_profile":
            info = ProfileFeature(self.client).get_info()
            self._collected_data["profile"] = info
            return info

        elif tool_name == "get_search_history":
            history = SearchFeature(self.client).get_search_history()
            return {"history": history}

        elif tool_name == "screenshot_and_tap":
            return self._screenshot_and_tap(args["description"])

        elif tool_name == "tap_screen":
            self.client.adb.tap(args["x"], args["y"])
            time.sleep(1.0)
            return f"已点击 ({args['x']}, {args['y']})"

        elif tool_name == "press_back":
            self.client.adb.press_key("KEYCODE_BACK")
            time.sleep(0.8)
            return "已按返回键"

        elif tool_name == "finish":
            return {"summary": args["summary"], "data": args.get("data", self._collected_data)}

        else:
            raise ValueError(f"未知工具: {tool_name}")

    def _analyze_filter_panel(self, screenshot_path: str, max_retries: int = 3) -> Optional[Dict]:
        """
        分析筛选面板截图，让 DeepSeek 一次性返回所有需要点击的坐标。
        带重试机制，每次失败把结果反馈给 DeepSeek。
        """
        import os, openai, numpy as np
        from PIL import Image

        if not os.path.exists(screenshot_path):
            return None

        arr = np.array(Image.open(screenshot_path))

        def analyze_screen(a: np.ndarray) -> str:
            h, w = a.shape[:2]
            dark_per_row = (a[:, :, :3].mean(axis=2) < 120).sum(axis=1)
            lines, cur = [], None
            for y in range(h):
                if dark_per_row[y] > 5:
                    cur = cur or {"ys": y, "ye": y}
                    cur["ye"] = y
                else:
                    if cur and cur["ye"] - cur["ys"] > 3:
                        yc = (cur["ys"] + cur["ye"]) // 2
                        row = a[cur["ys"]:cur["ye"]+1, :, :3].mean(axis=0)
                        dc = (row.mean(axis=1) < 120).nonzero()[0]
                        if len(dc) > 0:
                            xg, xc = [], None
                            for x in dc:
                                if xc is None: xc = [x]
                                elif x - xc[-1] < 20: xc.append(x)
                                else: xg.append((xc[0], xc[-1])); xc = [x]
                            if xc: xg.append((xc[0], xc[-1]))
                            xd = ", ".join(f"x={a_}~{b}(中心{(a_+b)//2})" for a_, b in xg[:5])
                            lines.append(f"  y={yc}: {xd}")
                    cur = None
            return (f"屏幕 {w}x{h}\n"
                    f"亮度: 顶(y=0~300)={a[:300,:,:3].mean():.0f}, "
                    f"中(y=700~1200)={a[700:1200,:,:3].mean():.0f}, "
                    f"底(y=1800+)={a[1800:,:,:3].mean():.0f}\n"
                    f"文字行:\n" + "\n".join(lines[:25]))

        api_key = os.getenv("DEEPSEEK_API_KEY")
        llm = openai.OpenAI(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        )

        screen_desc = analyze_screen(arr)
        messages = [
            {"role": "system", "content": (
                "你是 Android 手机自动化助手。根据屏幕像素分析（深色像素=文字/按钮），"
                "定位抖音筛选面板中的元素坐标。屏幕 1080x2340。"
                "面板布局从上到下：筛选标题、排序方式（综合/最新发布/最多点赞）、"
                "发布时间（不限/一天内/一周内/半年内）、视频时长、搜索范围、完成按钮。"
            )},
            {"role": "user", "content": (
                f"屏幕状态:\n{screen_desc}\n\n"
                "重要约束（已通过实验验证）：\n"
                "1. 面板是 bottom sheet，触摸区域从 y=390 开始，y<390 是遮罩点击会关闭面板\n"
                "2. 排序选项（综合/最新发布/最多点赞）：文字在 y≈310，但可点击区域在 y=390~450\n"
                "3. 点击'最新发布'后面板自动关闭，不需要点确认按钮\n\n"
                "请根据像素分析中排序选项的 X 坐标分布，只返回'最新发布'的坐标（JSON）：\n"
                "{\"latest\": {\"x\": 数字, \"y\": 数字}, "
                "\"reason\": \"说明\"}"
            )}
        ]

        last_feedback = ""
        for attempt in range(1, max_retries + 1):
            if last_feedback:
                messages.append({"role": "user", "content": f"上次结果反馈: {last_feedback}，请重新分析给出不同坐标。"})

            try:
                resp = llm.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                result = json.loads(resp.choices[0].message.content)
                messages.append({"role": "assistant", "content": resp.choices[0].message.content})
                logger.info(f"第{attempt}次分析: {result}")

                # 验证返回格式
                if "latest" in result:
                    return result
                last_feedback = f"返回格式不完整: {result}"

            except Exception as e:
                last_feedback = str(e)
                logger.error(f"第{attempt}次失败: {e}")

        return None

    def _screenshot_and_tap(self, description: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        截图 → DeepSeek 分析坐标 → 点击 → 截图确认 → 失败则把结果反馈给 DeepSeek 重试。
        最多重试 max_retries 次。
        """
        import subprocess, os, openai, numpy as np, time
        from PIL import Image

        api_key = os.getenv("DEEPSEEK_API_KEY")
        llm = openai.OpenAI(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        )

        def take_screenshot() -> np.ndarray:
            subprocess.run(["adb", "shell", "screencap", "-p", "/sdcard/_v.png"], capture_output=True)
            subprocess.run(["adb", "pull", "/sdcard/_v.png", "/tmp/_v.png"], capture_output=True)
            return np.array(Image.open("/tmp/_v.png"))

        def analyze_screen(arr: np.ndarray) -> str:
            """把截图转成文字描述（深色像素分布）"""
            h, w = arr.shape[:2]
            dark_per_row = (arr[:, :, :3].mean(axis=2) < 120).sum(axis=1)
            groups, cur = [], None
            for y in range(h):
                if dark_per_row[y] > 5:
                    cur = cur or {"y_start": y, "y_end": y}
                    cur["y_end"] = y
                else:
                    if cur and cur["y_end"] - cur["y_start"] > 3:
                        yc = (cur["y_start"] + cur["y_end"]) // 2
                        row = arr[cur["y_start"]:cur["y_end"]+1, :, :3].mean(axis=0)
                        dark_cols = (row.mean(axis=1) < 120).nonzero()[0]
                        if len(dark_cols) > 0:
                            xg, xc = [], None
                            for x in dark_cols:
                                if xc is None: xc = [x]
                                elif x - xc[-1] < 20: xc.append(x)
                                else: xg.append((xc[0], xc[-1])); xc = [x]
                            if xc: xg.append((xc[0], xc[-1]))
                            x_desc = ", ".join(f"x={a}~{b}(中心{(a+b)//2})" for a, b in xg[:5])
                            groups.append(f"  y={yc}: {x_desc}")
                    cur = None
            desc = f"屏幕 {w}x{h}，文字行:\n" + "\n".join(groups[:20])
            # 加上各区域亮度
            desc += f"\n亮度: 顶部(y=0~300)={arr[:300,:,:3].mean():.0f}, 中部(y=700~1200)={arr[700:1200,:,:3].mean():.0f}, 底部(y=1800+)={arr[1800:,:,:3].mean():.0f}"
            return desc

        messages = [{
            "role": "system",
            "content": (
                "你是 Android 手机自动化助手。根据屏幕像素分析结果（深色像素=文字/按钮位置），"
                "判断指定元素的坐标。屏幕分辨率 1080x2340。"
                "抖音筛选面板布局（从上到下）：筛选标题、排序方式（综合/最新发布/最多点赞）、"
                "发布时间（不限/一天内/一周内/半年内）、视频时长、搜索范围、完成按钮。"
                "只返回 JSON：{\"x\": 数字, \"y\": 数字, \"found\": true/false, \"reason\": \"说明\"}"
            )
        }]

        last_error = ""
        for attempt in range(1, max_retries + 1):
            arr = take_screenshot()
            screen_desc = analyze_screen(arr)

            user_msg = f"屏幕状态:\n{screen_desc}\n\n请找到「{description}」的坐标。"
            if last_error:
                user_msg += f"\n\n上次尝试失败：{last_error}，请重新分析并给出不同坐标。"

            messages.append({"role": "user", "content": user_msg})

            try:
                resp = llm.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                result = json.loads(resp.choices[0].message.content)
                messages.append({"role": "assistant", "content": resp.choices[0].message.content})
                logger.info(f"第{attempt}次分析: {result}")

                if not result.get("found", False):
                    last_error = f"DeepSeek 说未找到: {result.get('reason', '')}"
                    messages.append({"role": "user", "content": f"错误: {last_error}"})
                    continue

                x, y = int(result["x"]), int(result["y"])

                # 记录点击前的屏幕状态
                before_mid = arr[700:1200, :, :3].mean()

                self.client.adb.tap(x, y)
                time.sleep(0.8)

                # 截图确认结果
                after_arr = take_screenshot()
                after_mid = after_arr[700:1200, :, :3].mean()

                # 判断点击是否有效（屏幕发生了变化）
                diff = abs(float(before_mid) - float(after_mid))
                if diff < 5:
                    last_error = f"点击 ({x},{y}) 后屏幕无变化（中部亮度 {before_mid:.0f}→{after_mid:.0f}），坐标可能不准"
                    logger.warning(last_error)
                    messages.append({"role": "user", "content": f"点击结果: {last_error}"})
                    continue

                logger.info(f"点击成功: ({x},{y}) - {description}，屏幕变化 {before_mid:.0f}→{after_mid:.0f}")
                return {"success": True, "x": x, "y": y, "attempts": attempt}

            except Exception as e:
                last_error = str(e)
                logger.error(f"第{attempt}次失败: {e}")

        return {"success": False, "error": f"重试{max_retries}次后仍失败: {last_error}"}

    @staticmethod
    def _guess_page(labels: List[str]) -> str:
        label_set = set(labels)
        if label_set & {"历史记录", "猜你想搜"}:
            return "搜索输入页"
        if label_set & {"综合", "视频", "用户", "话题"}:
            return "搜索结果页"
        if any("推荐" in l and "按钮" in l for l in labels):
            return "推荐视频流"
        if "编辑主页" in label_set:
            return "个人主页"
        return "未知页面"
