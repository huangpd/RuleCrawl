"""
通用解析器（Universal Parser）
统一封装 XPath / CSS Selector / JsonPath / Regex 四种解析策略
"""

import re
import json
import logging
from typing import Any, Union
from lxml import etree
from parsel import Selector
from jsonpath_ng import parse as jsonpath_parse

logger = logging.getLogger(__name__)


class UniversalParser:
    """
    通用解析器，根据 selector_type 自动选择解析策略

    支持的类型：
    - xpath: XPath 表达式（基于 lxml）
    - css: CSS 选择器（基于 parsel）
    - jsonpath: JsonPath 表达式（基于 jsonpath-ng）
    - regex: 正则表达式（基于 re）
    """

    def __init__(self, content: Union[str, dict, list, Selector], content_type: str = "html"):
        """
        初始化解析器

        Args:
            content: 原始内容（HTML 字符串, JSON 对象, 或已有的 Selector 对象）
            content_type: 内容类型 html / json / text
        """
        self.raw_content = content
        self.content_type = content_type
        self._selector = None
        self._json_data = None

        if isinstance(content, Selector):
            self._selector = content
            self.content_type = "html"
            self.raw_content = content.get()
        elif content_type == "html":
            if isinstance(content, str):
                self._selector = Selector(text=content)
        elif content_type == "json":
            if isinstance(content, (dict, list)):
                self._json_data = content
            elif isinstance(content, str):
                try:
                    self._json_data = json.loads(content)
                except json.JSONDecodeError:
                    self._json_data = {}
                    logger.warning("Invalid JSON content provided")
            else:
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
        elif selector_type == "text":
            return [selector]
        else:
            raise ValueError(f"不支持的选择器类型: {selector_type}")

    def extract_first(
        self, selector: str, selector_type: str = "xpath", default: str = ""
    ) -> str:
        """提取第一个匹配结果"""
        results = self.extract(selector, selector_type)
        return results[0].strip() if results else default

    def extract_all(
        self, selector: str, selector_type: str = "xpath", default: str = ""
    ) -> str:

        results = self.extract(selector, selector_type)
        return ''.join(results) if results else default

    def extract_items(
        self, item_selector: str, selector_type: str = "xpath"
    ) -> list["UniversalParser"]:
        """
        列表页专用：按 item_selector 切割出子区块，返回子解析器列表
        """
        try:
            if selector_type == "xpath":
                if self._selector is not None:
                    items = self._selector.xpath(item_selector)
                    return [UniversalParser(item) for item in items]
            elif selector_type == "css":
                if self._selector is not None:
                    items = self._selector.css(item_selector)
                    return [UniversalParser(item) for item in items]
            elif selector_type == "jsonpath":
                if self._json_data is not None:
                    expr = jsonpath_parse(item_selector)
                    matches = expr.find(self._json_data)
                    return [UniversalParser(m.value, "json") for m in matches]
        except (ValueError, TypeError) as e:
            logger.error(f"Selector format error for {selector_type} '{item_selector}': {e}")
        except Exception as e:
            logger.error(f"Unexpected error extracting items with {selector_type} '{item_selector}': {e}")
        return []

    def _extract_xpath(self, selector: str) -> list[str]:
        """XPath 提取"""
        if self._selector is None:
            return []
        try:
            results = self._selector.xpath(selector).getall()
            return [str(r).strip() for r in results if str(r).strip()]
        except Exception as e:
            # lxml 可能抛出的异常类型较多，此处保留 Exception 但增加详细日志
            logger.error(f"XPath evaluation error '{selector}': {e}")
            return []

    def _extract_css(self, selector: str) -> list[str]:
        """CSS 选择器提取"""
        if self._selector is None:
            return []
        try:
            results = self._selector.css(selector).getall()
            return [r.strip() for r in results if r.strip()]
        except Exception as e:
            logger.error(f"CSS evaluation error '{selector}': {e}")
            return []

    def _extract_jsonpath(self, selector: str) -> list[str]:
        """JsonPath 提取"""
        if self._json_data is None:
            return []
        try:
            expr = jsonpath_parse(selector)
            matches = expr.find(self._json_data)
            results = []
            for m in matches:
                val = m.value
                if isinstance(val, (dict, list)):
                    # 对于复杂对象，返回标准 JSON 字符串
                    results.append(json.dumps(val, ensure_ascii=False))
                elif isinstance(val, str):
                    # 字符串直接返回，不做 strip 处理（除非确认为脏数据，但通用解析器不应随意修改数据）
                    results.append(val)
                else:
                    # 其他类型（int, bool 等）转字符串
                    results.append(str(val))
            return results
        except Exception as e:
            logger.error(f"JsonPath evaluation error '{selector}': {e}")
            return []

    def _extract_regex(self, selector: str) -> list[str]:
        """正则表达式提取"""
        try:
            content_str = self.raw_content
            # 如果 raw_content 不是字符串（如 JSON 对象），尝试转换为字符串
            if not isinstance(content_str, str):
                if self.content_type == "json" and self._json_data is not None:
                    content_str = json.dumps(self._json_data, ensure_ascii=False)
                else:
                    return []

            results = re.findall(selector, content_str)
            if results and isinstance(results[0], tuple):
                # 如果有分组，返回第一个分组
                return [r[0] for r in results]
            return results
        except re.error as e:
            logger.error(f"Regex syntax error '{selector}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in Regex extraction '{selector}': {e}")
            return []

    @staticmethod
    def apply_clean_rules(value: str, clean_rules: list[dict]) -> str:
        """
        应用字符串清洗规则（replace, trim, prefix, suffix, regex_sub）
        """
        if not value or not clean_rules:
            return value

        for rule in clean_rules:
            try:
                r_type = rule.get("type")
                if r_type == "trim":
                    value = value.strip()
                elif r_type == "replace":
                    old_val = rule.get("old", "")
                    new_val = rule.get("new", "")
                    value = value.replace(old_val, new_val)
                elif r_type == "regex_sub":
                    pattern = rule.get("old", "")
                    repl = rule.get("new", "")
                    if pattern:
                        value = re.sub(pattern, repl, value)
                elif r_type == "prefix":
                    prefix = rule.get("value", "")
                    value = prefix + value
                elif r_type == "suffix":
                    suffix = rule.get("value", "")
                    value = value + suffix
            except Exception as e:
                logger.error("清洗规则执行失败 [%s]: %s", rule.get("type"), e)
                # 继续执行后续规则，不中断流程
        
        return value
