"""
CyberHarvest Backend - FastAPI 服务
"""
import sys
import os

# 让 backend 能访问项目根目录的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from cyberharvest.backend.routers import search, system

app = FastAPI(title="CyberHarvest API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(system.router, prefix="/api/system", tags=["system"])


@app.get("/")
def root():
    return {"name": "CyberHarvest", "status": "running"}
