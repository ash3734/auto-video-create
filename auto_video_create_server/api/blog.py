from fastapi import APIRouter
from pydantic import BaseModel
from services.blog_shorts import extract_blog_content, get_blog_media_and_scripts

# 필요시 아래 함수들도 services. 경로로 import
# from services.summarize import ...
# from services.tts_fal import ...
# from services.create_creatomate_video import ...
# from services.extract_blog import ...

router = APIRouter()

class ExtractMediaRequest(BaseModel):
    blog_url: str

class ExtractMediaResponse(BaseModel):
    status: str
    images: list[str]
    videos: list[str]
    message: str = None

@router.post("/extract-media", response_model=ExtractMediaResponse)
def extract_media(req: ExtractMediaRequest):
    try:
        text, images, videos = extract_blog_content(req.blog_url)
        return {"status": "success", "images": images, "videos": videos}
    except Exception as e:
        return {"status": "error", "images": [], "videos": [], "message": str(e)}

@router.post("/extract-all")
def extract_all(req: ExtractMediaRequest):
    try:
        result = get_blog_media_and_scripts(req.blog_url)
        return {"status": "success", **result}
    except Exception as e:
        return {"status": "error", "message": str(e)} 