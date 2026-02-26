"""
HTTP 请求客户端封装
基于 httpx 异步客户端，复用连接池以提升性能
支持自动重试（最多 3 次，指数退避）
"""

import logging
from typing import Optional
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from app.config import DEFAULT_USER_AGENT, REQUEST_TIMEOUT
from app.utils.logger import get_logger

logger = get_logger("http_client")

# 全局共享的 AsyncClient 实例（通过 lifespan 管理生命周期）
_client: httpx.AsyncClient | None = None

# 需要重试的异常类型：网络超时、连接错误、读写错误
_RETRY_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)


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


@retry(
    stop=stop_after_attempt(3),                          # 最多重试 3 次
    wait=wait_exponential(multiplier=1, min=1, max=10),  # 退避：1s → 2s → 4s（上限 10s）
    retry=retry_if_exception_type(_RETRY_EXCEPTIONS),    # 仅对网络异常重试
    before_sleep=before_sleep_log(logger, logging.WARNING),  # 重试前打印日志
    reraise=True,                                        # 3 次全部失败后重新抛出异常
)
async def fetch(
    url: str,
    method: str = "GET",
    headers: Optional[dict] = None,
    cookies: Optional[dict] = None,
    body: Optional[str] = None,
    content_type: Optional[str] = None,
    timeout: int = REQUEST_TIMEOUT,
) -> httpx.Response:
    """
    发起 HTTP 请求（复用全局连接池，自动重试）

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

    Raises:
        httpx.TimeoutException / httpx.ConnectError 等: 3 次重试均失败后抛出
    """
    # 合并默认请求头
    final_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        final_headers.update(headers)
    if content_type:
        final_headers["Content-Type"] = content_type

    logger.info("HTTP 请求: %s %s", method, url)
    import time
    start_time = time.time()
    
    client = _client
    is_temp_client = False

    if client is None:
        # 降级：若全局客户端未初始化，创建临时客户端
        logger.warning("全局 HTTP 客户端未初始化，使用临时客户端（性能较低）")
        client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=False,
        )
        is_temp_client = True

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
        
        duration = time.time() - start_time
        logger.info("HTTP 响应: [%d] %s (耗时: %.2fs)", response.status_code, url, duration)
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error("HTTP 请求失败: %s %s (耗时: %.2fs, 错误: %s)", method, url, duration, e)
        raise e
    finally:
        # 仅关闭临时客户端
        if is_temp_client and client is not None:
            await client.aclose()
