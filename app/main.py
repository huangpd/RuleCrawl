"""
RuleCrawl — 基于规则的爬虫采集系统
FastAPI 应用入口
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import connect_db, close_db
from app.api.projects import router as projects_router
from app.api.nodes import router as nodes_router
from app.api.tasks import router as tasks_router
from app.api.data import router as data_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="RuleCrawl",
    description="基于规则的爬虫采集系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(projects_router)
app.include_router(nodes_router)
app.include_router(tasks_router)
app.include_router(data_router)


# 挂载前端静态文件
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "RuleCrawl"}
