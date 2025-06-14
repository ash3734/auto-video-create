from fastapi import FastAPI
from api.blog import router as blog_router
from mangum import Mangum
from fastapi.responses import JSONResponse
from fastapi import Request
import traceback

app = FastAPI()

handler = Mangum(app)

app.include_router(blog_router, prefix="/api/blog")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
