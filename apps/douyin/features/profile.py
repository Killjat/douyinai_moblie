"""
个人主页功能模块
- 获取主页信息（昵称、粉丝、关注、获赞）
- 获取粉丝列表
- 编辑个人简介
"""
import time
from typing import Dict, List, Any
from loguru import logger
from apps.douyin.client import DouyinClient


class ProfileFeature:
    """个人主页相关功能"""

    def __init__(self, client: DouyinClient):
        self.client = client

    def get_info(self) -> Dict[str, Any]:
        """获取个人主页信息"""
        try:
            self.client.ensure_open()
            nodes = self.client.navigate_to_profile()
            return self._parse(nodes)
        except Exception as e:
            logger.error(f"获取个人主页信息失败: {e}")
            return {}
        finally:
            self.client.return_to_feed()

    def get_follower_count(self) -> Dict[str, int]:
        """获取粉丝和关注数量"""
        info = self.get_info()
        return {"fans": info.get("fans", 0), "following": info.get("following", 0)}

    def get_followers_list(self) -> List[Dict[str, Any]]:
        """获取粉丝列表"""
        try:
            self.client.ensure_open()
            nodes = self.client.navigate_to_profile()

            fans_node = next((n for n in nodes if n.get("label", "").strip() == "粉丝"), None)
            if not fans_node:
                raise RuntimeError("未找到'粉丝'按钮")
            self.client.device.press(fans_node.get("ref"))

            nodes = self.client.wait_for_page(
                lambda ns: any("粉丝" in n.get("label", "") and n.get("label", "").strip() != "粉丝" for n in ns),
                timeout=10, desc="粉丝列表页"
            )
            followers = [{"name": n.get("label", "")} for n in nodes if "@" in n.get("label", "")]
            logger.info(f"提取到 {len(followers)} 个粉丝")
            return followers
        except Exception as e:
            logger.error(f"获取粉丝列表失败: {e}")
            return []
        finally:
            self.client.return_to_feed()

    def edit_bio(self, bio: str) -> bool:
        """编辑个人简介"""
        try:
            self.client.ensure_open()
            nodes = self.client.navigate_to_profile()

            edit_node = next((n for n in nodes if n.get("label", "").strip() == "编辑主页"), None)
            if not edit_node:
                raise RuntimeError("未找到'编辑主页'按钮")
            self.client.device.press(edit_node.get("ref"))

            nodes = self.client.wait_for_page(
                lambda ns: any(n.get("label", "").strip() == "简介" for n in ns),
                timeout=10, desc="编辑资料页"
            )
            bio_node = next(n for n in nodes if n.get("label", "").strip() == "简介")
            self.client.device.press(bio_node.get("ref"))
            time.sleep(0.5)

            self.client.adb.press_key("KEYCODE_CTRL_A")
            self.client.adb.press_key("KEYCODE_DEL")
            self.client.adb.input_text(bio)

            nodes = self.client.wait_for_page(
                lambda ns: any(n.get("label", "").strip() == "保存" for n in ns),
                timeout=5, desc="保存按钮"
            )
            save_node = next(n for n in nodes if n.get("label", "").strip() == "保存")
            self.client.device.press(save_node.get("ref"))

            logger.success(f"简介已更新: {bio}")
            return True
        except Exception as e:
            logger.error(f"编辑简介失败: {e}")
            return False
        finally:
            self.client.return_to_feed()

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------

    def _parse(self, nodes: List[Dict]) -> Dict[str, Any]:
        """
        字段命名与 ai_social_relationship 的 Neo4j User 节点对齐：
          nickname     ← 原 name
          douyin_id    ← 抖音号（新增采集）
          bio          ← 不变
          fans         ← 原 followers
          following    ← 不变
          total_likes  ← 原 likes
        """
        info = {
            "nickname": "",
            "douyin_id": "",
            "bio": "",
            "fans": 0,
            "following": 0,
            "total_likes": 0,
        }

        for i, node in enumerate(nodes):
            label = node.get("label", "").strip()
            if not label:
                continue

            # 昵称：抖音号节点往前找
            if label.startswith("抖音号：") and not info["nickname"]:
                info["douyin_id"] = label.replace("抖音号：", "").strip()
                for j in range(i - 1, max(i - 15, -1), -1):
                    prev = nodes[j].get("label", "").strip()
                    if prev and "切换" not in prev and "头像" not in prev:
                        info["nickname"] = prev
                        break

            elif label == "粉丝" and i > 0:
                num = nodes[i - 1].get("label", "").strip()
                if num.isdigit():
                    info["fans"] = int(num)

            elif label == "关注" and i > 0:
                num = nodes[i - 1].get("label", "").strip()
                if num.isdigit():
                    info["following"] = int(num)

            elif label == "获赞" and i > 0:
                num = nodes[i - 1].get("label", "").strip()
                if num.isdigit():
                    info["total_likes"] = int(num)

        logger.info(f"个人主页: {info}")
        return info
