
import asyncio
from app.engine.nodes.list_page import ListPageNode
from app.engine.context import CrawlContext
from app.engine.nodes.base import NodeResult

# 模拟 HTML (类似 quotes.toscrape.com)
HTML = """
<html>
<body>
    <div class="quote">
        <span class="text">“The world as we have created it is a process of our thinking. It cannot be changed without changing our thinking.”</span>
        <span>by <small class="author" itemprop="author">Albert Einstein</small>
        <a href="/author/Albert-Einstein">(about)</a>
        </span>
    </div>
</body>
</html>
"""

# 用户提供的配置
CONFIG = {
    "node_type": "list",
    "request_config": {},
    "parse_rules": {
        "parser_type": "xpath",
        "item_selector": "//div[@class=\"quote\"]/span",
        "item_selector_type": "xpath",
        "link_selector": ".//a/@href",
        "link_selector_type": "xpath",
        "fields": [
            {
                "name": "author",
                "selector": ".//small[@itemprop=\"author\"]/text()",
                "selector_type": "xpath",
                "is_link": False,
                "attr": None
            }
        ]
    }
}

async def test():
    node = ListPageNode(CONFIG)
    context = CrawlContext(url="http://example.com/page/1", html=HTML)
    
    result = await node.execute(context)
    
    print(f"Success: {result.success}")
    print(f"URLs: {result.urls}")
    print(f"URL Data: {result.url_data}")
    
    if result.urls:
        first_url = result.urls[0]
        if first_url in result.url_data:
            print(f"Data for {first_url}: {result.url_data[first_url]}")
        else:
            print(f"No data for {first_url}")

if __name__ == "__main__":
    asyncio.run(test())
