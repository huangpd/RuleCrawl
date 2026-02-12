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
### 2.5 静态文件服务崩溃 (WinError 123)
*   **事件**: 前端请求了包含非法字符（如引号、冒号）的路径（通常源于脏数据），导致 `StaticFiles` 在 Windows 下抛出 `OSError`，造成 500 错误。
*   **教训**: `StaticFiles` 默认未捕获文件系统错误。应继承并重写 `get_response` 方法，捕获 `OSError` / `ValueError` 并返回 404，以增强健壮性。

### 2.6 JsonPath 字符串提取
*   **事件**: `jsonpath-ng` 提取结果如果是字符串，可能保留了原始 JSON 的引号（取决于具体实现或数据源），导致数据包含 `"`。
*   **教训**: 对于文本类提取结果，尤其是 URL，建议在 `parser.py` 层统一做 `.strip("'\"")` 清理，防止脏数据入库。

### 2.7 前端数据展示安全及缓存
*   **事件**: 数据库中的脏数据（如包含引号的 URL）直接渲染到前端 HTML 中，导致浏览器将其解析为相对路径并发起错误请求。同时修改 JS 后未更新 `index.html` 的版本号导致用户用到旧缓存。
*   **教训**: 
    1.  **HTML 转义**: 在将用户数据拼接到 `innerHTML` 前，**必须**使用 `escapeHtml` 进行转义，既防止 XSS 也防止构造出意外的 HTML 标签（如 `<img src>`）导致资源自动加载。
    2.  **缓存失效**: 修改前端静态资源（JS/CSS）后，务必更新 `index.html` 引用链接中的版本号参数（如 `?v=1.2`），确保用户加载最新代码。

---
*最后更新*: 2026-02-12
