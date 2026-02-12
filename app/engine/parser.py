"""
通用解析器（Universal Parser）
统一封装 XPath / CSS Selector / JsonPath / Regex 四种解析策略
"""

import re
import json
from typing import Any
from lxml import etree
from parsel import Selector
from jsonpath_ng import parse as jsonpath_parse


class UniversalParser:
    """
    通用解析器，根据 selector_type 自动选择解析策略

    支持的类型：
    - xpath: XPath 表达式（基于 lxml）
    - css: CSS 选择器（基于 parsel）
    - jsonpath: JsonPath 表达式（基于 jsonpath-ng）
    - regex: 正则表达式（基于 re）
    """

    def __init__(self, content: str, content_type: str = "html"):
        """
        初始化解析器

        Args:
            content: 原始内容（HTML 或 JSON 字符串）
            content_type: 内容类型 html / json / text
        """
        self.raw_content = content
        self.content_type = content_type
        self._selector = None
        self._tree = None
        self._json_data = None

        if content_type == "html":
            self._tree = etree.HTML(content)
            self._selector = Selector(text=content)
        elif content_type == "json":
            try:
                self._json_data = json.loads(content)
            except json.JSONDecodeError:
                self._json_data = {}

    def extract(self, selector: str, selector_type: str = "xpath") -> list[str]:
        """
        通用提取方法，返回匹配结果列表

        Args:
            selector: 选择器表达式
            selector_type: 选择器类型（xpath/css/jsonpath/regex）

        Returns:
            匹配结果的字符串列表
        """
        if selector_type == "xpath":
            return self._extract_xpath(selector)
        elif selector_type == "css":
            return self._extract_css(selector)
        elif selector_type == "jsonpath":
            return self._extract_jsonpath(selector)
        elif selector_type == "regex":
            return self._extract_regex(selector)
        else:
            raise ValueError(f"不支持的选择器类型: {selector_type}")

    def extract_first(
        self, selector: str, selector_type: str = "xpath", default: str = ""
    ) -> str:
        """提取第一个匹配结果"""
        results = self.extract(selector, selector_type)
        return results[0].strip() if results else default

    def extract_items(
        self, item_selector: str, selector_type: str = "xpath"
    ) -> list["UniversalParser"]:
        """
        列表页专用：按 item_selector 切割出子区块，返回子解析器列表

        Args:
            item_selector: 列表项容器选择器
            selector_type: 选择器类型

        Returns:
            每个列表项的 UniversalParser 实例列表
        """
        if selector_type == "xpath":
            if self._tree is not None:
                elements = self._tree.xpath(item_selector)
                return [
                    UniversalParser(
                        etree.tostring(el, encoding="unicode", method="html"),
                        "html",
                    )
                    for el in elements
                ]
        elif selector_type == "css":
            if self._selector is not None:
                items = self._selector.css(item_selector)
                return [
                    UniversalParser(item.get(), "html") for item in items
                ]
        elif selector_type == "jsonpath":
            if self._json_data is not None:
                expr = jsonpath_parse(item_selector)
                matches = expr.find(self._json_data)
                return [
                    UniversalParser(json.dumps(m.value), "json") for m in matches
                ]
        return []

    def _extract_xpath(self, selector: str) -> list[str]:
        """XPath 提取"""
        if self._tree is None:
            return []
        try:
            results = self._tree.xpath(selector)
            return [str(r).strip() for r in results if str(r).strip()]
        except Exception:
            return []

    def _extract_css(self, selector: str) -> list[str]:
        """CSS 选择器提取"""
        if self._selector is None:
            return []
        try:
            results = self._selector.css(selector).getall()
            return [r.strip() for r in results if r.strip()]
        except Exception:
            return []

    def _extract_jsonpath(self, selector: str) -> list[str]:
        """JsonPath 提取"""
        if self._json_data is None:
            return []
        try:
            expr = jsonpath_parse(selector)
            matches = expr.find(self._json_data)
            return [str(m.value) for m in matches]
        except Exception:
            return []

    def _extract_regex(self, selector: str) -> list[str]:
        """正则表达式提取"""
        try:
            results = re.findall(selector, self.raw_content)
            if results and isinstance(results[0], tuple):
                # 如果有分组，返回第一个分组
                return [r[0] for r in results]
            return results
        except Exception:
            return []
