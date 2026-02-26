import asyncio
import json
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGODB_URI, DATABASE_NAME

async def inspect_config():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    
    # 查找雪球项目
    project = await db.projects.find_one({"name": {"$regex": "雪球"}})
    if not project:
        print("未找到名为 '雪球' 的项目")
        return

    print(f"项目名称: {project['name']}")
    print(f"项目 ID: {project['_id']}")
    print("="*50)

    # 查找该项目的所有节点
    cursor = db.nodes.find({"project_id": project['_id']}).sort("created_at", 1)
    async for node in cursor:
        print(f"节点类型: {node['node_type']}")
        print(f"节点名称: {node['name']}")
        print(f"请求配置: {json.dumps(node.get('request_config', {}), indent=2, ensure_ascii=False)}")
        print(f"解析规则: {json.dumps(node.get('parse_rules', {}), indent=2, ensure_ascii=False)}")
        print(f"回调目标: {node.get('callback_node_id')}")
        print("-" * 30)

if __name__ == "__main__":
    asyncio.run(inspect_config())
