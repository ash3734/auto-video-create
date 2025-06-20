from fastapi import APIRouter
from pydantic import BaseModel
from ..services.blog_shorts import extract_blog_content, get_blog_media_and_scripts
from ..services.summarize import summarize_for_shorts_sets
from ..services.tts_supertone import tts_with_supertone_multi
from ..services.create_creatomate_video import create_creatomate_video, get_creatomate_vars, poll_creatomate_video_url
import os
from typing import List, Optional, Literal
import requests

# 필요시 아래 함수들도 services. 경로로 import
# from ..services.summarize import ...
# from ..services.tts_fal import ...
# from ..services.create_creatomate_video import ...
# from ..services.extract_blog import ...

router = APIRouter()

class ExtractMediaRequest(BaseModel):
    blog_url: str

class ExtractMediaResponse(BaseModel):
    status: str
    images: list[str]
    videos: list[str]
    message: str = None

class SectionMedia(BaseModel):
    type: Literal["image", "video"]
    url: str

@router.get("/hello")
def hello():
    return {"message": "Hello, World!!!!!"}

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

# --- 최종 영상 생성 API ---
class GenerateVideoRequest(BaseModel):
    title: str
    scripts: List[str]
    sections: List[SectionMedia]  # 5개

class GenerateVideoResponse(BaseModel):
    status: str
    video_url: Optional[str] = None
    message: Optional[str] = None

@router.post("/generate-video")
def generate_video(req: GenerateVideoRequest):
    print("generate_video 호출")
    try:
        # 1. TTS 변환 (scripts → mp3 url)
        SUPERTONE_API_KEY = os.environ.get("SUPERTONE_API_KEY")
        SUPERTONE_VOICE_ID = "42b52760fe9ecf701f8ed3"
        SUPERTONE_SPEED = 1.4
        audio_local_paths, audio_urls = tts_with_supertone_multi(
            req.scripts,
            api_key=SUPERTONE_API_KEY,
            voice_id=SUPERTONE_VOICE_ID,
            speed=SUPERTONE_SPEED
        )
        audio_local_paths = audio_local_paths[:5]
        audio_urls = audio_urls[:5]

        # 2. 각 mp3 파일의 길이(초) 추출
        import mutagen
        from mutagen.mp3 import MP3
        durations = []
        for path in audio_local_paths:
            audio = MP3(path)
            durations.append(audio.info.length)
        creatomate_vars = get_creatomate_vars(durations)

        # 3. 섹션별 미디어 타입에 따라 Creatomate 변수 생성
        variables = {}
        for i, section in enumerate(req.sections, 1):
            if section.type == "image":
                variables[f"image{i}.source"] = section.url
                variables[f"image{i}.visible"] = "true"
                variables[f"video{i}.visible"] = "false"
            else:
                variables[f"video{i}.source"] = section.url
                variables[f"image{i}.visible"] = "false"
                variables[f"video{i}.visible"] = "true"

        # 4. Creatomate 영상 생성
        result = create_creatomate_video(
            audio_paths=audio_urls,
            scripts=req.scripts,
            title=req.title,
            **creatomate_vars,
            **variables
        )
        # Creatomate 응답에서 render_id 추출
        render_id = None
        if isinstance(result, list):
            result = result[0] if result else {}
        if isinstance(result, dict):
            render_id = result.get('id')
        if not render_id:
            return {"status": "error", "message": "Creatomate 응답에 렌더링 ID가 없습니다."}

        poll_url = f"https://api.creatomate.com/v1/renders/{render_id}"
        return {"status": "started", "render_id": render_id, "poll_url": poll_url}
    except Exception as e:
        print("[generate_video 에러]", e)
        return {"status": "error", "message": str(e)}

@router.get("/poll-video")
def poll_video(render_id: str):
    CREATOMATE_API_KEY = os.environ["CREATOMATE_API_KEY"]
    url = f"https://api.creatomate.com/v1/renders/{render_id}"
    headers = {"Authorization": f"Bearer {CREATOMATE_API_KEY}"}
    resp = requests.get(url, headers=headers)
    return resp.json() 
