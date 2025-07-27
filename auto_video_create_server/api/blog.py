from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from services.blog_shorts import extract_blog_content, get_blog_media_and_scripts
from services.summarize import summarize_for_shorts_sets
from services.tts_supertone import tts_with_supertone_multi
from services.create_creatomate_video import create_creatomate_video, get_creatomate_vars, poll_creatomate_video_url
from services.account_service import get_user_if_active
from utils.s3_utils import load_json_from_s3
import os
from typing import List, Optional, Literal
import requests
import traceback
from urllib.parse import urlparse

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

def validate_blog_url(user_id: str, blog_url: str) -> bool:
    """
    사용자의 블로그 주소와 요청된 블로그 주소를 비교하여 검증
    네이버 블로그의 경우: blog.naver.com/사용자명 형태로 비교
    test 사용자이고 테스트 서버일 경우 검증을 건너뜀
    """
    try:
        # test 사용자이고 테스트 서버일 경우 검증 건너뛰기
        if user_id == "test" and os.environ.get("ENV").lower() == 'test':
            print(f"테스트 서버에서 test 사용자 블로그 검증 건너뛰기: {blog_url}")
            return True
        # S3에서 사용자 데이터 로드
        users_data = load_json_from_s3("blog-to-short-form-users", "users.json")
        
        # 사용자 찾기
        user = None
        for u in users_data:
            if u["id"] == user_id:
                user = u
                break
        
        if not user:
            print(f"사용자를 찾을 수 없음: {user_id}")
            return False
        
        # 사용자의 블로그 주소 확인
        user_blog_url = user.get("blog_url")
        if not user_blog_url:
            print(f"사용자 {user_id}의 블로그 주소가 설정되지 않음")
            return False
        
        # URL 파싱하여 도메인과 첫 번째 디렉토리명 비교
        def parse_blog_url(url):
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path_parts = parsed.path.strip('/').split('/')
            username = path_parts[0] if path_parts else ""
            return domain, username
        
        user_domain, user_username = parse_blog_url(user_blog_url)
        request_domain, request_username = parse_blog_url(blog_url)
        
        print(f"사용자 블로그: {user_domain}/{user_username}")
        print(f"요청 블로그: {request_domain}/{request_username}")
        
        # 도메인과 사용자명 모두 일치하는지 확인
        return user_username == request_username
        
    except Exception as e:
        print(f"블로그 URL 검증 중 오류: {e}")
        return False

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
        
        # 블로그 URL 검증
        user_id = user["id"]
        if not validate_blog_url(user_id, req.blog_url):
            return {
                "status": "error", 
                "message": "등록된 블로그 주소가 아닙니다. 관리자에게 문의하여 블로그 주소를 등록해주세요."
            }
        
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
