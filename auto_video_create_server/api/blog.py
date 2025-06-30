from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from services.blog_shorts import extract_blog_content, get_blog_media_and_scripts
from services.summarize import summarize_for_shorts_sets
from services.tts_supertone import tts_with_supertone_multi
from services.create_creatomate_video import create_creatomate_video, get_creatomate_vars, poll_creatomate_video_url
from services.account_service import get_user_if_active
import os
from typing import List, Optional, Literal
import requests
import traceback

# 필요시 아래 함수들도 services. 경로로 import
# from services.summarize import ...
# from services.tts_fal import ...
# from services.create_creatomate_video import ...
# from services.extract_blog import ...

def require_active_subscription(request: Request):
    user_id = request.headers.get("X-USER-ID") or request.query_params.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="인증 정보가 없습니다.")
    user = get_user_if_active(user_id)
    if not user:
        raise HTTPException(status_code=403, detail="구독이 만료된 계정입니다.")
    return user

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

@router.post("/extract-all")
def extract_all(req: ExtractMediaRequest, user=Depends(require_active_subscription)):
    try:
        print("extract_all 시작")
        result = get_blog_media_and_scripts(req.blog_url)
        print("extract_all 성공")
        print("extract_all 응답 반환 직전")
        return {"status": "success", **result}
    except Exception as e:
        print("extract_all 에러:", e)
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        print("extract_all finally 블록 실행")

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
def generate_video(req: GenerateVideoRequest, user=Depends(require_active_subscription)):
    print("generate_video 호출")
    try:
        # 1. TTS 변환 (scripts → mp3 url)
        SUPERTONE_API_KEY = os.environ.get("SUPERTONE_API_KEY")
        SUPERTONE_VOICE_ID = "c9220df3a5a70647d7b022"
        SUPERTONE_SPEED = 1.4
        audio_local_paths, audio_urls = tts_with_supertone_multi(
            req.scripts,
            api_key=SUPERTONE_API_KEY,
            voice_id=SUPERTONE_VOICE_ID,
            speed=SUPERTONE_SPEED
        )
        audio_local_paths = audio_local_paths[:5]
        audio_urls = audio_urls[:5]

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
def poll_video(render_id: str, user=Depends(require_active_subscription)):
    CREATOMATE_API_KEY = os.environ["CREATOMATE_API_KEY"]
    url = f"https://api.creatomate.com/v1/renders/{render_id}"
    headers = {"Authorization": f"Bearer {CREATOMATE_API_KEY}"}
    resp = requests.get(url, headers=headers)
    return resp.json() 
