"""
RuleCrawl 核心下载引擎
支持多驱动架构 (Httpx / Curl-Cffi / Playwright)
"""

import time
import httpx
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.config import DEFAULT_USER_AGENT, REQUEST_TIMEOUT
from app.utils.logger import get_logger
from app.models.download import DownloadResponse # 领域对齐命名

logger = get_logger("core.downloader")

class BaseDownloader(ABC):
    """下载器抽象接口"""
    @abstractmethod
    async def fetch(self, url: str, **kwargs) -> DownloadResponse:
        pass

    @abstractmethod
    async def close(self):
        pass

_RETRY_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)

class HttpxDownloader(BaseDownloader):
    """基于 HTTPX 的高性能异步下载器实现"""
    _client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                verify=False,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, 30),
        reraise=True,
    )
    async def fetch(self, url: str, **kwargs) -> DownloadResponse:
        method = kwargs.get("method", "GET").upper()
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        if custom_headers := kwargs.get("headers"):
            headers.update({k: str(v) for k, v in custom_headers.items()})

        params = kwargs.get("params")
        body = kwargs.get("body")
        body_type = kwargs.get("body_type", "json")

        # 处理 POST 请求体格式
        content = None
        if method == "POST" and body:
            if body_type == "json":
                headers["Content-Type"] = "application/json"
                content = body # 假设 body 已经是 JSON 字符串
            else:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                content = body # httpx 会自动处理字符串格式的 form body

        client = await self._get_client()
        start_time = time.time()

        try:
            resp = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                content=content,
                cookies=kwargs.get("cookies"),
                timeout=kwargs.get("timeout", REQUEST_TIMEOUT)
            )

            duration = time.time() - start_time
            logger.info("HTTPX [%d] %s (%.2fs)", resp.status_code, url, duration)

            resp_ct = resp.headers.get("content-type", "").lower()
            content_type = "html"
            if "json" in resp_ct: content_type = "json"
            elif "xml" in resp_ct: content_type = "xml"
            elif "text/plain" in resp_ct: content_type = "text"

            return DownloadResponse(
                url=str(resp.url),
                status_code=resp.status_code,
                text=resp.text,
                content=resp.content,
                headers=dict(resp.headers),
                cookies=dict(resp.cookies),
                content_type=content_type,
                elapsed=duration,
                success=resp.status_code < 400
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error("HTTPX 崩溃 %s: %s (%.2fs)", url, e, duration)
            return DownloadResponse(
                url=url, status_code=0, success=False, error=str(e), elapsed=duration
            )

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

class DownloaderFactory:
    """下载器单例工厂"""
    _instances: Dict[str, BaseDownloader] = {}

    @classmethod
    async def get_downloader(cls, downloader_type: str = "httpx") -> BaseDownloader:
        if downloader_type not in cls._instances:
            if downloader_type == "httpx":
                cls._instances[downloader_type] = HttpxDownloader()
            else:
                raise ValueError(f"不支持的下载器类型: {downloader_type}")
        return cls._instances[downloader_type]

    @classmethod
    async def close_all(cls):
        for downloader in cls._instances.values():
            await downloader.close()
        cls._instances.clear()
