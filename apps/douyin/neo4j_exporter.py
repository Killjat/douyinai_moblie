"""
Neo4j 导出器 — 将手机端采集的数据写入 Neo4j 图谱

节点/关系结构与 ai_social_relationship 的 graph_service.py 完全一致：
  节点：
    User — nickname, douyin_id, bio, fans, following, total_likes, source
    Work — work_id, type, likes, title, source
  关系：
    (User)-[:PUBLISHED]->(Work)

source 字段标记数据来源：
  "mobile"  — 本项目（手机端）采集
  "web"     — ai_social_relationship（Web 端）采集
"""
import os
import hashlib
from typing import Dict, Any, List, Optional
from loguru import logger

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("neo4j 未安装，请运行: pip install neo4j")

from config.settings import settings


class Neo4jExporter:
    """将手机端采集数据写入 Neo4j 图谱"""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self.driver = None

    def connect(self) -> bool:
        if not NEO4J_AVAILABLE:
            logger.error("neo4j 包未安装")
            return False
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()
            self._ensure_indexes()
            logger.success(f"Neo4j 连接成功: {self.uri}")
            return True
        except Exception as e:
            logger.error(f"Neo4j 连接失败: {e}")
            return False

    def close(self):
        if self.driver:
            self.driver.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------
    # 索引
    # ------------------------------------------------------------------

    def _ensure_indexes(self):
        with self.driver.session() as s:
            # douyin_id 可能为空（Web 端部分数据），只对非空值建索引
            s.run("CREATE INDEX user_nickname IF NOT EXISTS FOR (u:User) ON (u.nickname)")
            s.run("CREATE CONSTRAINT work_id IF NOT EXISTS FOR (w:Work) REQUIRE w.work_id IS UNIQUE")

    # ------------------------------------------------------------------
    # 写入 User 节点（来自 ProfileFeature.get_info()）
    # ------------------------------------------------------------------

    def export_profile(self, profile: Dict[str, Any]) -> bool:
        """
        写入用户节点。
        profile 字段：nickname, douyin_id, bio, fans, following, total_likes
        """
        douyin_id = profile.get("douyin_id", "").strip()
        if not douyin_id:
            logger.warning(f"profile 缺少 douyin_id，跳过: {profile.get('nickname')}")
            return False
        try:
            with self.driver.session() as s:
                s.run("""
                    MERGE (u:User {douyin_id: $douyin_id})
                    SET u.nickname    = $nickname,
                        u.bio         = $bio,
                        u.fans        = $fans,
                        u.following   = $following,
                        u.total_likes = $total_likes,
                        u.source      = 'mobile',
                        u.updated_at  = timestamp()
                """,
                    douyin_id=douyin_id,
                    nickname=profile.get("nickname", ""),
                    bio=profile.get("bio", ""),
                    fans=profile.get("fans", 0),
                    following=profile.get("following", 0),
                    total_likes=profile.get("total_likes", 0),
                )
            logger.info(f"User 写入成功: {profile.get('nickname')} ({douyin_id})")
            return True
        except Exception as e:
            logger.error(f"export_profile 失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 写入 Work 节点（来自 FeedFeature.scan()）
    # ------------------------------------------------------------------

    def export_feed(self, videos: List[Dict[str, Any]]) -> int:
        """
        批量写入视频节点，并建立 (User)-[:PUBLISHED]->(Work) 关系。
        video 字段：nickname, type, title, likes, comment_count, shares
        注：手机端无 work_id/url，用 nickname+title 的 hash 作为临时 work_id
        """
        count = 0
        for video in videos:
            if self._export_work(video):
                count += 1
        logger.info(f"Feed 导出完成: {count}/{len(videos)} 条")
        return count

    def _export_work(self, video: Dict[str, Any]) -> bool:
        nickname = video.get("nickname", "").strip()
        title = video.get("title", "").strip()
        if not nickname:
            return False

        # 手机端无 work_id，用 nickname+title hash 生成临时 ID（前缀 mobile_）
        raw = f"{nickname}:{title}"
        work_id = "mobile_" + hashlib.md5(raw.encode()).hexdigest()[:12]

        try:
            with self.driver.session() as s:
                # 写入 Work 节点和 PUBLISHED 关系
                s.run("""
                    MERGE (w:Work {work_id: $work_id})
                    SET w.type          = $type,
                        w.title         = $title,
                        w.likes         = $likes,
                        w.comment_count = $comment_count,
                        w.shares        = $shares,
                        w.source        = 'mobile',
                        w.updated_at    = timestamp()
                    WITH w
                    MERGE (u:User {nickname: $nickname})
                    MERGE (u)-[:PUBLISHED]->(w)
                """,
                    work_id=work_id,
                    type=video.get("type", "视频"),
                    title=title,
                    likes=video.get("likes", ""),
                    comment_count=video.get("comment_count", ""),
                    shares=video.get("shares", ""),
                    nickname=nickname,
                )
                
                # 处理评论数据
                comments = video.get("comments", [])
                if comments:
                    for comment in comments:
                        comment_user = comment.get("user", "").strip()
                        comment_content = comment.get("content", "").strip()
                        if comment_user and comment_content:
                            # 生成评论的唯一 ID
                            comment_raw = f"{work_id}:{comment_user}:{comment_content}"
                            comment_id = "comment_" + hashlib.md5(comment_raw.encode()).hexdigest()[:12]
                            
                            # 写入 Comment 节点和相关关系
                            s.run("""
                                MERGE (c:Comment {comment_id: $comment_id})
                                SET c.content     = $content,
                                    c.source       = 'mobile',
                                    c.updated_at   = timestamp()
                                WITH c
                                MATCH (w:Work {work_id: $work_id})
                                MERGE (w)-[:HAS_COMMENT]->(c)
                                WITH c
                                MERGE (u:User {nickname: $comment_user})
                                MERGE (u)-[:COMMENTED]->(c)
                            """,
                                comment_id=comment_id,
                                content=comment_content,
                                work_id=work_id,
                                comment_user=comment_user,
                            )
            return True
        except Exception as e:
            logger.error(f"_export_work 失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 写入直播数据（来自 LiveFeature.collect()）
    # ------------------------------------------------------------------

    def export_live(self, live_info) -> bool:
        """
        写入直播主播的 User 节点，并记录直播快照数据。
        live_info: LiveInfo dataclass 或 dict
        """
        import dataclasses
        data = dataclasses.asdict(live_info) if dataclasses.is_dataclass(live_info) else live_info

        nickname = data.get("nickname", "").strip()
        if not nickname:
            logger.warning("live_info 缺少 nickname，跳过")
            return False

        try:
            with self.driver.session() as s:
                # 更新主播 User 节点（仅更新直播相关字段）
                s.run("""
                    MERGE (u:User {nickname: $nickname})
                    SET u.live_viewer_count = $viewer_count,
                        u.live_total_likes  = $total_likes,
                        u.live_updated_at   = timestamp(),
                        u.source            = CASE WHEN u.source IS NULL THEN 'mobile' ELSE u.source END
                """,
                    nickname=nickname,
                    viewer_count=data.get("viewer_count", ""),
                    total_likes=data.get("total_likes", ""),
                )
            logger.info(f"Live 写入成功: {nickname}, 在线={data.get('viewer_count')}")
            return True
        except Exception as e:
            logger.error(f"export_live 失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, int]:
        with self.driver.session() as s:
            users = s.run("MATCH (u:User) RETURN count(u) AS n").single()["n"]
            works = s.run("MATCH (w:Work) RETURN count(w) AS n").single()["n"]
            comments = s.run("MATCH (c:Comment) RETURN count(c) AS n").single()["n"]
            rels = s.run("MATCH ()-[r:PUBLISHED]->() RETURN count(r) AS n").single()["n"]
            comment_rels = s.run("MATCH ()-[r:HAS_COMMENT|COMMENTED]->() RETURN count(r) AS n").single()["n"]
            mobile = s.run("MATCH (n) WHERE n.source='mobile' RETURN count(n) AS n").single()["n"]
        return {"users": users, "works": works, "comments": comments, "published": rels, "comment_relations": comment_rels, "mobile_nodes": mobile}

    # ------------------------------------------------------------------
    # 跨端关联查询
    # ------------------------------------------------------------------

    def find_related_works(self, nickname: str = None, title: str = None) -> List[Dict]:
        """
        查找两端都采集到的同一视频（通过 nickname + title 软匹配）。
        返回 web 端和 mobile 端的节点对。

        用法：
            # 查某作者的所有跨端视频
            exporter.find_related_works(nickname="方明泉摄影")

            # 查特定标题
            exporter.find_related_works(title="西大街30年巨变")
        """
        conditions = []
        params = {}
        if nickname:
            conditions.append("u1.nickname = $nickname AND u2.nickname = $nickname")
            params["nickname"] = nickname
        if title:
            conditions.append("w1.title CONTAINS $title AND w2.title CONTAINS $title")
            params["title"] = title

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            MATCH (u1:User)-[:PUBLISHED]->(w1:Work {{source: 'web'}}),
                  (u2:User)-[:PUBLISHED]->(w2:Work {{source: 'mobile'}})
            {where}
            AND w1.title = w2.title
            RETURN u1.nickname AS nickname,
                   w1.work_id  AS web_work_id,
                   w1.title    AS title,
                   w1.likes    AS web_likes,
                   w1.url      AS url,
                   w2.work_id  AS mobile_work_id,
                   w2.likes    AS mobile_likes,
                   w2.comment_count AS comment_count,
                   w2.shares   AS shares
        """
        with self.driver.session() as s:
            result = s.run(query, **params)
            return [dict(r) for r in result]
