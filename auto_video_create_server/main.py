from fastapi import FastAPI
from api.blog import router as blog_router
from mangum import Mangum

app = FastAPI()
app.include_router(blog_router, prefix="/api/blog")

handler = Mangum(app)
