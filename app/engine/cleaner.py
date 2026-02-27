"""
RuleCrawl 数据清洗引擎 (Clean Pipeline)
提供原子化、可组合的字段清洗能力
"""

import re
from abc import ABC, abstractmethod
from typing import List, Any, Union
from functools import reduce
from app.models.node import CleanRule
from app.utils.logger import get_logger

logger = get_logger("engine.cleaner")

class CleanHandler(ABC):
    @abstractmethod
    def handle(self, value: str) -> str: pass

class TrimHandler(CleanHandler):
    def handle(self, value: str) -> str: return value.strip() if value else ""

class ReplaceHandler(CleanHandler):
    def __init__(self, old: str, new: str):
        self.old, self.new = old or "", new or ""
    def handle(self, value: str) -> str: return value.replace(self.old, self.new) if value else ""

class RegexSubHandler(CleanHandler):
    def __init__(self, pattern: str, repl: str):
        self.pattern, self.repl = pattern or "", repl or ""
    def handle(self, value: str) -> str:
        if not value or not self.pattern: return value
        try: return re.sub(self.pattern, self.repl, value)
        except Exception as e:
            logger.warning(f"Regex清洗失败: {e}")
            return value

class PrefixHandler(CleanHandler):
    def __init__(self, val: str): self.val = val or ""
    def handle(self, value: str) -> str: return self.val + value

class SuffixHandler(CleanHandler):
    def __init__(self, val: str): self.val = val or ""
    def handle(self, value: str) -> str: return value + self.val

class CleanHandlerFactory:
    @staticmethod
    def create(rule_input: Any) -> CleanHandler:
        # ── 核心修复：确保输入始终为 CleanRule 模型 ──
        rule = rule_input if isinstance(rule_input, CleanRule) else CleanRule(**rule_input)
        
        rt = rule.type
        if rt == "trim": return TrimHandler()
        if rt == "replace": return ReplaceHandler(rule.old, rule.new)
        if rt == "regex_sub": return RegexSubHandler(rule.old, rule.new)
        if rt == "prefix": return PrefixHandler(rule.value)
        if rt == "suffix": return SuffixHandler(rule.value)
        raise ValueError(f"不支持的清洗类型: {rt}")

class CleanPipeline:
    def __init__(self, rules: List[Any]):
        # 预加载所有处理器
        self.handlers = [CleanHandlerFactory.create(r) for r in (rules or [])]

    def process(self, value: str) -> str:
        if not value: return ""
        try:
            return reduce(lambda v, h: h.handle(v), self.handlers, value)
        except Exception as e:
            logger.error(f"Pipeline 执行异常: {e}")
            return value
