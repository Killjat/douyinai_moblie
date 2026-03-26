"""
抖音自动化客户端
"""
import re
from typing import Dict, List, Any, Optional
from loguru import logger
from core.device_controller import DeviceController
from config.settings import settings


class DouyinClient:
    """抖音自动化客户端"""

    def __init__(self, device_id: Optional[str] = None):
        """初始化抖音客户端

        Args:
            device_id: 设备 ID
        """
        self.device = DeviceController(device_id)
        self.logger = logger

    def open_douyin(self) -> bool:
        """打开抖音应用

        Returns:
            是否成功打开
        """
        try:
            # 尝试通过文本查找抖音图标
            result = self.device.press_text("抖音")
            if result:
                logger.info("成功打开抖音")
                return True

            # 如果找不到，尝试通过其他方式打开
            logger.warning("未找到抖音图标，尝试其他方式...")
            return False
        except Exception as e:
            logger.error(f"打开抖音失败: {e}")
            return False

    def get_follower_count(self) -> Dict[str, int]:
        """获取粉丝和关注数量

        Returns:
            包含 followers 和 following 的字典
        """
        try:
            # 点击进入个人主页
            self.device.press_text("我")
            self.logger.info("进入个人主页")

            # 获取快照
            snapshot = self.device.get_snapshot()
            nodes = snapshot.get("nodes", [])

            result = {"followers": 0, "following": 0}

            # 查找粉丝和关注数量
            # 抖音界面中，数字和标签是分开的节点，需要通过位置关系匹配
            for i, node in enumerate(nodes):
                label = node.get("label", "").strip()

                # 检查是否是数字节点
                if re.match(r'^\d+$', label):
                    # 查看下一个或上一个节点是什么
                    prev_label = nodes[i-1].get("label", "").strip() if i > 0 else ""
                    next_label = nodes[i+1].get("label", "").strip() if i < len(nodes)-1 else ""

                    if prev_label == "粉丝" or next_label == "粉丝":
                        result["followers"] = int(label)
                        self.logger.info(f"粉丝数量: {result['followers']}")

                    elif prev_label == "关注" or next_label == "关注":
                        result["following"] = int(label)
                        self.logger.info(f"关注数量: {result['following']}")

                # 兼容格式如 "10 粉丝" 在同一个节点的情况
                if re.search(r'\d+\s*粉丝', label) and "关注" not in label:
                    match = re.search(r'(\d+)\s*粉丝', label)
                    if match:
                        result["followers"] = int(match.group(1))
                        self.logger.info(f"粉丝数量: {result['followers']}")

                # 兼容格式如 "10 关注" 在同一个节点的情况
                if re.search(r'\d+\s*关注', label) and "粉丝" not in label:
                    match = re.search(r'(\d+)\s*关注', label)
                    if match:
                        result["following"] = int(match.group(1))
                        self.logger.info(f"关注数量: {result['following']}")

            return result
        except Exception as e:
            self.logger.error(f"获取粉丝数量失败: {e}")
            return {"followers": 0, "following": 0}

    def extract_followers_list(self) -> List[Dict[str, Any]]:
        """提取粉丝列表

        Returns:
            粉丝列表数据
        """
        followers = []

        try:
            # 点击进入个人主页
            self.device.press_text("我")
            self.logger.info("进入个人主页")

            # 点击粉丝数量
            self.device.press_text("粉丝")
            self.logger.info("进入粉丝列表")

            # 获取快照
            snapshot = self.device.get_snapshot()
            nodes = snapshot.get("nodes", [])

            # 提取粉丝信息
            for node in nodes:
                label = node.get("label", "")
                if label and "@" in label:
                    followers.append({"name": label})
                    self.logger.info(f"粉丝: {label}")

            return followers
        except Exception as e:
            self.logger.error(f"提取粉丝列表失败: {e}")
            return followers

    def edit_profile_bio(self, bio: str) -> bool:
        """编辑个人简介

        Args:
            bio: 新的简介内容

        Returns:
            是否成功编辑
        """
        try:
            # 进入个人主页
            self.device.press_text("我")
            self.logger.info("进入个人主页")

            # 点击编辑按钮 (通常在右上角)
            snapshot = self.device.get_snapshot()
            nodes = snapshot.get("nodes", [])

            # 查找编辑或更多按钮
            for node in nodes:
                label = node.get("label", "")
                if label in ["编辑", "编辑资料", "更多"]:
                    ref = node.get("ref")
                    self.device.press_by_ref(ref)
                    break

            # 点击简介输入框
            self.device.press_text("简介")

            # 清空现有内容
            import time
            from core.adb_manager import ADBManager
            adb = ADBManager()
            adb.press_key("KEYCODE_CTRL_A")
            adb.press_key("KEYCODE_DEL")

            # 输入新内容
            adb.input_text(bio)

            # 保存
            self.device.press_text("保存")

            self.logger.info(f"简介已更新为: {bio}")
            return True
        except Exception as e:
            self.logger.error(f"编辑简介失败: {e}")
            return False

    def get_profile_info(self) -> Dict[str, Any]:
        """获取个人主页信息

        Returns:
            个人主页信息
        """
        try:
            import time
            import subprocess

            # 先返回首页
            self.logger.info("返回首页...")
            subprocess.run(
                ["agent-device", "home", "--json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            time.sleep(1.5)

            # 点击"我"按钮
            self.logger.info("点击'我'按钮进入个人主页...")
            me_nodes = []
            snapshot = self.device.get_snapshot()
            nodes = snapshot.get("nodes", [])

            # 查找纯"我"字的节点
            for node in nodes:
                if node.get("label", "").strip() == "我":
                    me_nodes.append(node)

            if me_nodes:
                ref = me_nodes[0].get("ref")
                self.logger.info(f"找到'我'按钮: {ref}")
                self.device.press(ref)
            else:
                self.logger.warning("未找到'我'按钮")

            # 等待页面加载
            time.sleep(2)

            # 获取个人主页快照
            snapshot = self.device.get_snapshot()
            nodes = snapshot.get("nodes", [])

            info = {
                "name": "",
                "bio": "",
                "followers": 0,
                "following": 0,
                "likes": 0
            }

            import re
            for node in nodes:
                label = node.get("label", "")
                if label:
                    # 查找用户名 (通常是 @ 开头的)
                    if "@" in label and not info["name"] and label.count("@") == 1:
                        info["name"] = label
                        self.logger.info(f"找到昵称: {label}")
                    # 查找粉丝数量 (格式如 "10 粉丝")
                    elif "粉丝" in label and "关注" not in label:
                        match = re.search(r'(\d+).*粉丝', label)
                        if match:
                            info["followers"] = int(match.group(1))
                            self.logger.info(f"粉丝数: {label}")
                    # 查找关注数量 (格式如 "10 关注")
                    elif "关注" in label and "粉丝" not in label:
                        match = re.search(r'(\d+).*关注', label)
                        if match:
                            info["following"] = int(match.group(1))
                            self.logger.info(f"关注数: {label}")
                    # 查找获赞数量
                    elif "获赞" in label:
                        match = re.search(r'(\d+).*获赞', label)
                        if match:
                            info["likes"] = int(match.group(1))
                            self.logger.info(f"获赞数: {label}")

            self.logger.info(f"个人主页信息: {info}")
            return info
        except Exception as e:
            self.logger.error(f"获取个人信息失败: {e}")
            import traceback
            traceback.print_exc()
            return {}
