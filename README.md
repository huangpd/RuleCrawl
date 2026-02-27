# RuleCrawl — 分布式可视化规则爬虫系统

RuleCrawl 是一个现代化的、基于规则的可视化采集平台。在最新的版本中，系统已从单机架构进化为**分布式任务总线架构**，支持海量数据采集、分布式水平扩展以及任务断点续爬。

## ✨ 核心特性

-   **分布式调度**：基于 **RabbitMQ** 实现任务分发，支持多个爬虫节点（Worker）协同工作。
-   **任务韧性 (Snapshot)**：利用持久化队列实现“断点续爬”，系统重启或崩溃后可自动恢复任务进度。
-   **分布式控制**：通过控制总线（Control Bus）广播信号，支持跨节点统一停止采集任务。
-   **工业级日志**：统一的彩色日志管理系统，支持模块追踪与详尽的 Exception 堆栈分析。
-   **全能解析**：支持 XPath、CSS Selector、**JsonPath**、Regex 及通配符 URL 遍历。
-   **内存安全**：采用分块（Chunking）与背压控制，彻底杜绝海量 URL 导致的内存溢出。

## 🏛️ 分布式系统架构

```mermaid
graph TB
    subgraph Frontend["前端 (HTML + JS)"]
        TabUI["3 标签页编辑器"]
        DataView["数据检索与管理"]
    end

    subgraph API["FastAPI 集群 (无状态)"]
        ProjectAPI["项目管理 API"]
        TaskAPI["任务控制 (信号广播)"]
        DataAPI["数据检索 (模糊搜索)"]
    end

    subgraph Broker["RabbitMQ 消息中间件"]
        TaskQueue["任务队列 (持久化)"]
        ControlBus["控制总线 (信号广播)"]
    end

    subgraph Engine["分布式 Worker 集群"]
        FlowMgr["Flow Manager (消费/分发)"]
        NodeRunner["节点处理器 (Pydantic 驱动)"]
        Parser["Universal Parser"]
    end

    subgraph Storage["MongoDB"]
        ConfigCol["配置/任务元数据"]
        DataCol["采集结果集 (data_store)"]
    end

    Frontend --> API
    API --> ControlBus
    API --> TaskQueue
    API --> Storage
    ControlBus -. 停止信号 .-> FlowMgr
    TaskQueue -- 任务分发 --> FlowMgr
    FlowMgr --> NodeRunner
    NodeRunner --> Parser
    NodeRunner -- 数据入库 --> Storage
```

## 🔄 分布式数据流转

1.  **任务启动**：API 接收到请求，通过 `StartNode` 生成初始种子并推送到 RabbitMQ 任务队列。
2.  **分布式处理**：多个 Worker 同时监听队列。每个 Worker 领取任务后，根据规则执行抓取并解析。
3.  **裂变分发**：列表页产生的子链接再次包装成任务推回 RabbitMQ，实现任务的自动分裂。
4.  **背压保护**：通过设置 MQ `prefetch_count`，确保每个 Worker 节点负载恒定。
5.  **信号拦截**：通过广播交换机，UI 下达的停止指令能瞬间同步到所有正在运行的 Worker。

## 🛠️ 技术栈

-   **核心框架**: Python 3.9+, FastAPI
-   **分布式通信**: **RabbitMQ (aio-pika)**
-   **解析引擎**: Parsel, Lxml, JsonPath-ng, Regex
-   **数据存储**: MongoDB 4.4+ (Motor Async Driver)
-   **前端交互**: 原生 HTML5/CSS3 (Glassmorphism), Vanilla JS

## 🚀 快速开始

### 1. 环境准备
确保已安装 MongoDB 和 **RabbitMQ** 服务。

### 2. 配置环境
创建 `.env` 文件：
```ini
MONGODB_URI=mongodb://localhost:27017
DATABASE_NAME=rulecrawl
RABBITMQ_URL=amqp://guest:guest@localhost/
```

### 3. 安装并启动
```bash
pip install .
uvicorn app.main:app --reload --port 8000
```

## 📖 高级技巧：模式解析

在起始页 URL 中，支持通配符模式：
-   **页码遍历**：`https://example.com/list_{offset(1,100)}.html`
-   **多行输入**：起始页支持一次性粘贴多个独立 URL 或模式。

## 📄 许可证
MIT License
