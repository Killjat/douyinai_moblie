"""
配置管理模块
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载 .env 文件 - 从项目根目录
BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv()  # 尝试从当前目录加载

class Settings:
    """应用配置类"""

    # 项目根目录
    BASE_DIR = Path(__file__).parent.parent

    # 输出目录
    OUTPUT_DIR = BASE_DIR / "output"
    SCREENSHOTS_DIR = BASE_DIR / "screenshots"
    LOGS_DIR = BASE_DIR / "logs"

    # CyberStroll 配置
    CYBERSTROLL_BIO = "CyberStroll 跨境电商 - 专注于为全球消费者提供优质商品和购物体验"

    # 超时配置
    SNAPSHOT_TIMEOUT = 10
    WAIT_TIMEOUT = 5

    # DeepSeek AI 配置
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    def __init__(self):
        """初始化并创建必要的目录"""
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
