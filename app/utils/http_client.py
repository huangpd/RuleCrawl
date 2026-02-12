"""
HTTP 请求客户端封装
基于 httpx 异步客户端，支持自定义 Headers/Cookies
"""

import httpx
from app.config import DEFAULT_USER_AGENT, REQUEST_TIMEOUT


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
    发起 HTTP 请求

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

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        verify=False,
    ) as client:
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
