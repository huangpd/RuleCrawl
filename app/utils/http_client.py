"""
HTTP 请求客户端封装
基于 httpx 异步客户端，复用连接池以提升性能
"""

import logging
import httpx
from app.config import DEFAULT_USER_AGENT, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# 全局共享的 AsyncClient 实例（通过 lifespan 管理生命周期）
_client: httpx.AsyncClient | None = None


async def init_client():
    """初始化全局 HTTP 客户端（在 FastAPI lifespan 中调用）"""
    global _client
    _client = httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        verify=False,
        limits=httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20,
        ),
    )
    logger.info("HTTP 客户端已初始化（连接池已就绪）")


async def close_client():
    """关闭全局 HTTP 客户端（在 FastAPI lifespan 中调用）"""
    global _client
    if _client:
        await _client.aclose()
        _client = None
        logger.info("HTTP 客户端已关闭")


async def fetch(
    url: str,
    method: str = "GET",
    headers: dict = None,
    cookies: dict = None,
    body: str = None,
    content_type: str = None,
    timeout: int = REQUEST_TIMEOUT,
) -> httpx.Response:
    """
    发起 HTTP 请求（复用全局连接池）

    Args:
        url: 请求目标 URL
        method: GET 或 POST
        headers: 自定义请求头
        cookies: 自定义 Cookies
        body: POST 请求体
        content_type: Content-Type
        timeout: 超时秒数

    Returns:
        httpx.Response 响应对象
    """
    # 合并默认请求头
    final_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        final_headers.update(headers)
    if content_type:
        final_headers["Content-Type"] = content_type

    logger.info("HTTP 请求: %s %s", method, url)
    client = _client
    if client is None:
        # 降级：若全局客户端未初始化，创建临时客户端
        logger.warning("全局 HTTP 客户端未初始化，使用临时客户端（性能较低）")
        client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=False,
        )

    try:
        if method.upper() == "POST":
            response = await client.post(
                url,
                headers=final_headers,
                cookies=cookies or {},
                content=body,
            )
        else:
            response = await client.get(
                url,
                headers=final_headers,
                cookies=cookies or {},
            )
        return response
    finally:
        # 仅关闭临时客户端
        if _client is None and client is not None:
            await client.aclose()
