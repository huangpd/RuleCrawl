"""
RuleCrawl 节点模块初始化
负责加载所有节点类型以触发自注册机制
"""

from . import start
from . import list_page
from . import detail

# 这样外部只需 import app.engine.nodes 即可完成所有类的加载
