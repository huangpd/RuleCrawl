"""
RuleCrawl 配置模块
从 .env 文件或环境变量中读取配置
"""

import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB 配置
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/admin")
DATABASE_NAME = os.getenv("DATABASE_NAME", "rulecrawl")

# 服务器配置
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# 爬虫引擎配置
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30  # 秒
MAX_CONCURRENT_REQUESTS = 10  # 最大并发请求数
DEFAULT_MAX_PAGES = 100  # 默认最大翻页数
