"""
RuleCrawl 上下文模型
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class TaskContext:
    url: str
    project_id: str
    task_id: str
    parent_data: Dict[str, Any] = field(default_factory=dict)
    # ── 新增：在节点间流转的动态凭证 ──
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    
    page_number: int = 1
    depth: int = 0
    source_url: str = ""

    def clone(self, **overrides) -> "TaskContext":
        import dataclasses
        current = dataclasses.asdict(self)
        current.update(overrides)
        return TaskContext(**current)
