"""FastAPI 应用入口。

该文件负责：
1. 创建 FastAPI 应用对象
2. 初始化数据库表
3. 注册企业相关接口路由
"""

from fastapi import FastAPI

from backend import models
from backend.api.enterprise import router as enterprise_router
from backend.database import engine

# 启动时根据 ORM 模型自动创建表结构。
# 当前项目使用的是 SQLite，本地首次运行时会自动生成对应表。
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Nanhai Data Map API",
    description="南海区数据产业企业图谱后端服务",
    version="1.0.0"
)

# 挂载企业管理相关接口，最终会暴露为 /enterprises 路径。
app.include_router(enterprise_router)


@app.get("/")
def root():
    """提供最基础的健康检查接口，确认服务是否正常启动。"""
    return {"message": "Nanhai Data Map API is running"}
