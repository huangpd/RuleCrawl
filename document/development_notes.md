# 开发注意事项与关键逻辑文档

本文档记录 RuleCrawl 项目中的关键逻辑实现细节以及历史踩坑经验，旨在帮助后续开发中避免重复错误。每次修复重要 Bug 或修改核心逻辑后，请更新此文档。

## 1. 核心逻辑实现

### 1.1 列表页数据透传 (List Page Field Passthrough)
*   **机制**: 列表页 (`ListPageNode`) 在提取链接的同时，可以提取非链接字段（如作者、日期）。
*   **数据流**:
    1. `ListPageNode` 将提取的额外字段存储在 `NodeResult.url_data` (Key: 子URL, Value: 字段字典)。
    2. `FlowManager` 在创建子任务 `CrawlContext` 时，读取 `url_data` 并注入到 `child_context.parent_data`。
    3. `DetailNode` (`DetailNode`) 在执行时，先读取 `context.parent_data`，再与本页提取的数据合并。
*   **注意**: 即使是 JsonPath 提取模式（生成 `data://` 假链接），透传逻辑依然适用。

### 1.2 `data://` 协议与 JsonPath 提取
*   **场景**: 当列表页返回的是 JSON 数据而非 HTML 链接时（通常配置 item_selector 为 jsonpath），`FlowManager` 会生成 `data://{uuid}` 格式的虚拟 URL，并将 JSON 对象序列化后注入 `context.html`。
*   **处理**:
    *   `DetailNode` 必须识别 `data://` 协议，**跳过** `fetch` 网络请求。
    *   **关键点**: 在初始化 `UniversalParser` 时，必须显式指定 `content_type="json"`。否则解析器默认按 HTML 处理，导致 JsonPath 提取失败。
    ```python
    if context.url.startswith("data://"):
        content_type = "json"
        # ...
    parser = UniversalParser(html, content_type=content_type)
    ```

### 1.3 HTTP 请求客户端 (`app/utils/http_client.py`)
*   **fetch 函数签名**:
    ```python
    async def fetch(url, method="GET", headers=None, cookies=None, body=None, content_type=None, timeout=...)
    ```
*   **避坑**: `fetch` 函数**不接受** `proxy` 参数。代理配置在全局 `init_client` 或环境变量中处理。切勿在调用时传入 `proxy`，否则会报错 `unexpected keyword argument`。

### 1.4 基类方法 (`BaseNode`)
*   **辅助方法**: `BaseNode` 提供了 `merge_headers(context_headers)` 和 `merge_cookies(context_cookies)` 方法。
*   **继承**: 所有具体节点类（DetailNode, ListPageNode）都应使用这些方法来合并上下文传递的头信息和配置中的头信息，确保 User-Agent 等关键信息不丢失。

## 2. 历史 Bug 与教训 (Pitfalls)

### 2.1 缩进错误 (IndentationError)
*   **事件**: 在移除 `if db is not None` 判断层级时，忘记将内部代码块反缩进，导致语法错误。
*   **教训**: 修改控制流结构（尤其是移除 if/try 块）后，务必检查后续代码块的缩进层级。

### 2.2 方法缺失 (AttributeError)
*   **事件**: 在 `DetailNode` 中调用 `self.merge_headers`，但该方法在父类 `BaseNode` 中并未定义（或被遗漏），导致运行时崩溃。
*   **教训**: 在使用父类方法前，确认其确实存在。如果需要通用功能，优先在 `BaseNode` 中实现，而不是在子类中临时硬编码。

### 2.3 协议不支持 (Unsupported Protocol)
*   **事件**: `DetailNode` 直接将 `data://` URL 传给 `fetch` 函数，导致底层库报错。
*   **教训**: 任何涉及 URL 的网络请求，都应考虑是否存在非 HTTP 协议（如 `data://`, `file://`），并在发起请求前做防御性检查。

### 2.4 解析模式不匹配
*   **事件**: 将 JSON 字符串传给默认的 `UniversalParser`（默认 html 模式），导致无法用 JsonPath 提取数据。
*   **教训**: 解析器初始化时必须明确内容的类型（HTML vs JSON），不能假设解析器能自动探测。

---
*最后更新*: 2026-02-12
