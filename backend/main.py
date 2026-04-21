from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import models
from backend.api.enterprise import router as enterprise_router
from backend.database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Nanhai Data Map API",
    description="南海区数据产业图谱后端服务",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(enterprise_router)


@app.get("/")
def root():
    return {"message": "南海区数据产业图谱后端服务运行中"}
