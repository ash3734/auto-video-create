from fastapi import FastAPI
from api.blog import router as blog_router
from fastapi.responses import JSONResponse
from fastapi import Request
import traceback

app = FastAPI()
app.include_router(blog_router, prefix="/api/blog")

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
