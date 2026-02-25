# 在 main.py 或单独调试文件
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",  # 你的应用路径
        host="0.0.0.0",
        port=8080,
        reload=True,     # 支持热重载
    )