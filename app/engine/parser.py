"""
通用解析引擎 (Universal Parser) - 策略模式重构版
支持 XPath / CSS / JsonPath / Regex 的可扩展架构
"""

import re
import json
from abc import ABC, abstractmethod
from typing import Any, Union, List, Dict
from parsel import Selector
from jsonpath_ng import parse as jsonpath_parse
from app.utils.logger import get_logger

logger = get_logger("engine.parser")

class ParserStrategy(ABC):
    """解析策略基类"""
    @abstractmethod
    def extract(self, content: Any, selector: str) -> List[str]:
        pass

class XPathStrategy(ParserStrategy):
    def extract(self, content: Selector, selector: str) -> List[str]:
        if content is None: return []
        try:
            return [str(r).strip() for r in content.xpath(selector).getall() if str(r).strip()]
        except Exception as e:
            logger.error(f"XPath 解析错误 '{selector}': {e}")
            return []

class CSSStrategy(ParserStrategy):
    def extract(self, content: Selector, selector: str) -> List[str]:
        if content is None: return []
        try:
            return [r.strip() for r in content.css(selector).getall() if r.strip()]
        except Exception as e:
            logger.error(f"CSS 解析错误 '{selector}': {e}")
            return []

class JsonPathStrategy(ParserStrategy):
    def extract(self, content: Any, selector: str) -> List[str]:
        if content is None: return []
        try:
            expr = jsonpath_parse(selector)
            matches = expr.find(content)
            results = []
            for m in matches:
                val = m.value
                if isinstance(val, (dict, list)):
                    results.append(json.dumps(val, ensure_ascii=False))
                else:
                    results.append(str(val))
            return results
        except Exception as e:
            logger.error(f"JsonPath 解析错误 '{selector}': {e}")
            return []

class RegexStrategy(ParserStrategy):
    def extract(self, content: str, selector: str) -> List[str]:
        if not isinstance(content, str): return []
        try:
            results = re.findall(selector, content)
            if results and isinstance(results[0], tuple):
                return [r[0] for r in results]
            return [str(r) for r in results]
        except Exception as e:
            logger.error(f"Regex 解析错误 '{selector}': {e}")
            return []

class TextStrategy(ParserStrategy):
    """原样返回策略"""
    def extract(self, content: Any, selector: str) -> List[str]:
        return [selector]

# 策略注册表
PARSER_STRATEGIES: Dict[str, ParserStrategy] = {
    "xpath": XPathStrategy(),
    "css": CSSStrategy(),
    "jsonpath": JsonPathStrategy(),
    "regex": RegexStrategy(),
    "text": TextStrategy()
}

class UniversalParser:
    """
    通用解析器上下文
    """
    def __init__(self, content: Union[str, dict, list, Selector], content_type: str = "html"):
        self.raw_content = content
        self.content_type = content_type
        self._selector = None
        self._json_data = None

        if isinstance(content, Selector):
            self._selector = content
            self.raw_content = content.get()
        elif content_type == "html":
            if isinstance(content, str): self._selector = Selector(text=content)
        elif content_type == "json":
            if isinstance(content, (dict, list)):
                self._json_data = content
            elif isinstance(content, str):
                try: self._json_data = json.loads(content)
                except: self._json_data = {}

    def extract(self, selector: str, selector_type: str = "xpath") -> List[str]:
        """
        利用策略模式执行提取
        """
        strategy = PARSER_STRATEGIES.get(selector_type)
        if not strategy:
            raise ValueError(f"不支持的解析类型: {selector_type}")

        # 根据内容类型分发给策略
        target = self._json_data if selector_type == "jsonpath" else \
                 (self.raw_content if selector_type == "regex" else self._selector)
        
        return strategy.extract(target, selector)

    def extract_first(self, selector: str, selector_type: str = "xpath", default: str = "") -> str:
        res = self.extract(selector, selector_type)
        return res[0] if res else default

    def extract_all(self, selector: str, selector_type: str = "xpath", default: str = "") -> str:
        res = self.extract(selector, selector_type)
        return "".join(res) if res else default

    def extract_items(self, item_selector: str, selector_type: str = "xpath") -> List["UniversalParser"]:
        """
        切割列表项并产生新的解析器实例
        """
        try:
            if selector_type == "xpath" and self._selector:
                return [UniversalParser(it) for it in self._selector.xpath(item_selector)]
            if selector_type == "css" and self._selector:
                return [UniversalParser(it) for it in self._selector.css(item_selector)]
            if selector_type == "jsonpath" and self._json_data:
                expr = jsonpath_parse(item_selector)
                return [UniversalParser(m.value, "json") for m in expr.find(self._json_data)]
        except Exception as e:
            logger.error(f"提取 Item 失败: {e}")
        return []

    @staticmethod
    def apply_clean_rules(value: str, clean_rules: List[Any]) -> str:
        """
        利用 CleanPipeline 执行清洗 (解耦后的调用)
        """
        from app.engine.cleaner import CleanPipeline
        return CleanPipeline(clean_rules).process(value)
