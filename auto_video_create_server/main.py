from fastapi import FastAPI, Response, Query
from pydantic import BaseModel
from auto_video_create_server.crawler.naver import extract_blog_content
import requests

app = FastAPI()

class ExtractMediaRequest(BaseModel):
    blog_url: str

class ExtractMediaResponse(BaseModel):
    status: str
    images: list[str]
    videos: list[str]
    message: str = None

@app.post("/api/extract-media", response_model=ExtractMediaResponse)
def extract_media(req: ExtractMediaRequest):
    try:
        text, images, videos = extract_blog_content(req.blog_url)
        return {"status": "success", "images": images, "videos": videos}
    except Exception as e:
        return {"status": "error", "images": [], "videos": [], "message": str(e)}

@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}

@app.get("/api/image-proxy")
def image_proxy(url: str = Query(..., description="이미지 원본 URL")):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg")
        return Response(content=r.content, media_type=content_type)
    except Exception as e:
        return Response(content=b"", status_code=404) 