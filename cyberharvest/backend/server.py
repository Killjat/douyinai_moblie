"""
PyInstaller 打包入口 - 启动 FastAPI 后端服务
"""
import sys
import os

# 打包后资源路径处理
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
    sys.path.insert(0, base_dir)
    # 设置项目根目录
    project_root = os.path.join(base_dir, "_internal", "project")
    if os.path.exists(project_root):
        sys.path.insert(0, project_root)
else:
    base_dir = os.path.join(os.path.dirname(__file__), "../..")
    sys.path.insert(0, os.path.abspath(base_dir))

import uvicorn

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18765
    uvicorn.run(
        "cyberharvest.backend.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
