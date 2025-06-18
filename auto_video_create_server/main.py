from fastapi import FastAPI
from api.blog import router as blog_router
from mangum import Mangum
from fastapi.responses import JSONResponse
from fastapi import Request
import traceback
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

load_dotenv()

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").split(",")
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"] ,
)

app.include_router(blog_router, prefix="/api/blog")

handler = Mangum(app)

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

@app.get("/hello")
def hello():
    return {"message": "Hello, World!!!!!"}

@app.get("/hello2")
def hello():
    return {"message": "Hello, World!!!!!"}