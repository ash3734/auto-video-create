from fastapi import FastAPI
from api.blog import router as blog_router
from mangum import Mangum
from fastapi.responses import JSONResponse
from fastapi import Request
import traceback

print("=== main.py: FastAPI 인스턴스 생성 시작 ===")
app = FastAPI()
print("=== main.py: FastAPI 인스턴스 생성 완료 ===")

app.include_router(blog_router, prefix="/api/blog")
print("=== main.py: blog_router 등록 완료 ===")

handler = Mangum(app)
print("=== main.py: Mangum 핸들러 생성 완료 ===")

@app.get("/hello")
def hello():
    print("=== /hello 엔드포인트 호출됨 ===")
    return {"message": "Hello, World!!!!!"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print("=== [FastAPI Unhandled Exception] ===")
    print("Request:", request.url)
    print("Exception:", exc)
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc)},
    )

@app.get("/hello2")
def hello():
    return {"message": "Hello, World!!!!!"}
