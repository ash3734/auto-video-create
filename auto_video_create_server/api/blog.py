from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from services.blog_shorts import extract_blog_content, get_blog_media_and_scripts
from services.summarize import summarize_for_shorts_sets
from services.tts_supertone import tts_with_supertone_multi
from services.create_creatomate_video import create_creatomate_video, get_creatomate_vars, poll_creatomate_video_url
from services.account_service import get_user_if_active, check_user_credits, get_current_credits
from services.ai_background import generate_backgrounds_parallel, FALLBACK_URL as DEFAULT_BG_FALLBACK_URL
from services.image_mirror import maybe_mirror
# cycle-3: 자막 스타일 편집 신규 서비스
from services.font_service import get_korean_fonts, get_allowed_font_families
from services.subtitle_settings_service import (
    get_subtitle_settings,
    save_subtitle_settings,
    validate_subtitle_settings,
    apply_subtitle_settings_to_variables,
)
from crawler.dispatcher import UnsupportedPlatformError
from utils.s3_utils import load_json_from_s3
import os
from typing import Any, Dict, List, Optional, Literal
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

def require_active_subscription_and_credits(request: Request, required_credits: int = 1000):
    """구독 상태와 크레딧을 모두 체크하는 함수"""
    user_id = request.headers.get("X-USER-ID") or request.query_params.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="인증 정보가 없습니다.")
    
    # 구독 상태 체크
    user = get_user_if_active(user_id)
    if not user:
        raise HTTPException(status_code=403, detail="구독이 만료된 계정입니다.")
    
    # 크레딧 체크
    if not check_user_credits(user_id, required_credits):
        current_credits = get_current_credits(user_id)
        raise HTTPException(
            status_code=402, 
            detail=f"크레딧이 부족합니다. 현재 보유 크레딧: {current_credits}개, 필요 크레딧: {required_credits}개"
        )
    
    return user

def validate_blog_url(user_id: str, blog_url: str) -> bool:
    """
    사용자의 블로그 주소와 요청된 블로그 주소를 비교하여 검증
    네이버 블로그의 경우: blog.naver.com/사용자명 형태로 비교
    test 사용자이고 테스트 서버일 경우 검증을 건너뜀
    """
    try:
        # test 사용자이고 테스트 서버일 경우 검증 건너뛰기
        if user_id == "test" and os.environ.get("ENV", "").lower() == 'test':
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
        
        # URL 파싱: 플랫폼별 username 추출 규칙 (cycle-2: tistory / brunch 추가)
        def parse_blog_url(url):
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            path = parsed.path.strip('/')
            path_parts = path.split('/') if path else []

            # 네이버: blog.naver.com/{username}
            if "blog.naver.com" in host:
                username = path_parts[0] if path_parts else ""
                return "naver", username

            # 티스토리: {username}.tistory.com
            if host.endswith(".tistory.com"):
                subdomain = host.replace(".tistory.com", "")
                return "tistory", subdomain

            # 브런치: brunch.co.kr/@{username}
            if "brunch.co.kr" in host:
                first = path_parts[0] if path_parts else ""
                username = first[1:] if first.startswith("@") else first
                return "brunch", username

            # 그 외: 도메인 자체를 username 으로 (개인 도메인은 1차 사이클 미지원이지만 fallback)
            return host, ""

        user_platform, user_username = parse_blog_url(user_blog_url)
        request_platform, request_username = parse_blog_url(blog_url)

        print(f"사용자 블로그: {user_platform}/{user_username}")
        print(f"요청 블로그: {request_platform}/{request_username}")

        # 플랫폼과 사용자명 모두 일치해야 통과
        return (user_platform == request_platform) and (user_username == request_username) and user_username != ""
        
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
    # cycle-2: 신규 필드 (BE 내부 사용 / 디버깅 / FE 는 default_slot_count 만 사용)
    category: Optional[Literal["restaurant", "general"]] = None
    platform: Optional[Literal["naver", "tistory", "brunch"]] = None
    default_slot_count: Optional[int] = 0
    message: str = None


class SectionMedia(BaseModel):
    # cycle-2: 'default' 추가 — BE 가 generate-video 시점에 AI 배경 생성
    type: Literal["image", "video", "default"]
    url: Optional[str] = None
    isDefaultBackground: Optional[bool] = False

@router.get("/hello")
def hello():
    return {"message": "Hello, World!!!!!"}

@router.post("/extract-all")
def extract_all(req: ExtractMediaRequest, user=Depends(require_active_subscription)):
    try:
        print("extract_all 시작")

        # cycle-2 (D-1): validate_blog_url 활성화. ENV=test 환경은 함수 내부에서 우회.
        user_id = user["id"]
        if not validate_blog_url(user_id, req.blog_url):
            return {
                "status": "error",
                "error_code": "blog_not_registered",
                "message": "등록된 블로그 주소가 아닙니다. 관리자에게 문의해주세요.",
            }

        result = get_blog_media_and_scripts(req.blog_url)
        print("extract_all 성공")
        return {"status": "success", **result}
    except UnsupportedPlatformError as e:
        # cycle-2: 비지원 플랫폼 (네이버 / 티스토리 / 브런치 외)
        print(f"extract_all 비지원 플랫폼: {e}")
        return {
            "status": "error",
            "error_code": "unsupported_platform",
            "message": "지원하지 않는 블로그 플랫폼이에요. 네이버 블로그, 티스토리, 브런치만 가능해요.",
        }
    except Exception as e:
        print("extract_all 에러:", e)
        traceback.print_exc()
        return {
            "status": "error",
            "error_code": "crawl_failed",
            "message": "블로그를 불러올 수 없어요. 다른 글로 시도해주세요.",
        }
    finally:
        print("extract_all finally 블록 실행")

# ─────────────────────────────────────────────
# cycle-3: 자막 스타일 관련 Pydantic 모델
# ─────────────────────────────────────────────

class TextStyleModel(BaseModel):
    font_family: str
    font_size: str       # "S" / "M" / "L"
    fill_color: str      # "#RRGGBB"


class SubtitleSettingsModel(BaseModel):
    title: TextStyleModel
    subtitle: TextStyleModel


class SubtitleSettingsRequest(BaseModel):
    title: TextStyleModel
    subtitle: TextStyleModel


# --- 최종 영상 생성 API ---
class GenerateVideoRequest(BaseModel):
    title: str
    scripts: List[str]
    sections: List[SectionMedia]  # 5개
    # cycle-3: optional — 없으면 Creatomate 템플릿 기본값 유지
    subtitle_settings: Optional[SubtitleSettingsModel] = None

class GenerateVideoResponse(BaseModel):
    status: str
    video_url: Optional[str] = None
    message: Optional[str] = None

@router.post("/generate-video")
def generate_video(req: GenerateVideoRequest, user=Depends(require_active_subscription_and_credits)):
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
        # cycle-2: type='default' 슬롯은 AI 배경을 lazy 병렬 생성 (ADR-4).
        default_pairs = [
            (i, req.scripts[i] if i < len(req.scripts) else "")
            for i, section in enumerate(req.sections)
            if section.type == "default"
        ]
        ai_bg_urls = {}
        if default_pairs:
            print(f"[generate_video] AI 배경 병렬 생성 — 슬롯 {[idx for idx, _ in default_pairs]}")
            try:
                ai_bg_urls = generate_backgrounds_parallel(default_pairs, max_workers=5)
            except Exception as e:
                # 병렬 호출 전체 실패 시 fallback URL 로 채움
                print(f"[generate_video] AI 배경 생성 실패 — fallback 전체 적용: {e}")
                ai_bg_urls = {idx: DEFAULT_BG_FALLBACK_URL for idx, _ in default_pairs}

        variables = {}
        for i, section in enumerate(req.sections, 1):
            zero_idx = i - 1
            if section.type == "image":
                # cycle-2.2 BUG-007: Creatomate 가 차단당하는 외부 호스트(Daum CDN 등) 는
                # S3 미러링 후 그 URL 을 전달. 그 외 호스트는 원본 그대로.
                image_src = maybe_mirror(section.url or "", referer="https://brunch.co.kr/")
                variables[f"image{i}.source"] = image_src
                variables[f"image{i}.visible"] = "true"
                variables[f"video{i}.visible"] = "false"
            elif section.type == "video":
                variables[f"video{i}.source"] = section.url
                variables[f"image{i}.visible"] = "false"
                variables[f"video{i}.visible"] = "true"
            else:  # 'default' — AI 생성 배경 (이미지로 처리)
                bg_url = ai_bg_urls.get(zero_idx, DEFAULT_BG_FALLBACK_URL)
                variables[f"image{i}.source"] = bg_url
                variables[f"image{i}.visible"] = "true"
                variables[f"video{i}.visible"] = "false"

        # 4. cycle-3: subtitle_settings 가 있으면 Creatomate modifications 에 주입
        if req.subtitle_settings:
            apply_subtitle_settings_to_variables(
                variables,
                req.subtitle_settings.model_dump(),
            )
            print(
                f"[generate_video] subtitle_settings 주입 완료 "
                f"(title_font={req.subtitle_settings.title.font_family}, "
                f"subtitle_font={req.subtitle_settings.subtitle.font_family})"
            )

        # 5. Creatomate 영상 생성 (user_id 전달)
        result = create_creatomate_video(
            audio_paths=audio_urls,
            scripts=req.scripts,
            title=req.title,
            user_id=user["id"],  # 크레딧 체크/차감을 위해 user_id 전달
            **variables
        )
        # Creatomate 응답 처리
        if isinstance(result, dict) and result.get("error"):
            # 크레딧 부족 등의 에러 응답
            return {
                "status": "error", 
                "message": result.get("message", "영상 생성 실패"),
                "error_type": result.get("error")
            }
        
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

@router.get("/credits")
def get_user_credits(user=Depends(require_active_subscription)):
    """사용자의 현재 크레딧 정보 조회"""
    user_id = user["id"]
    current_credits = get_current_credits(user_id)
    return {
        "status": "success",
        "user_id": user_id,
        "current_credits": current_credits,
        "required_credits": 1000
    }


# ─────────────────────────────────────────────
# cycle-3 신규 엔드포인트
# ─────────────────────────────────────────────

@router.get("/fonts")
def get_fonts(user=Depends(require_active_subscription)):
    """
    GET /api/blog/fonts

    한글 지원 폰트 목록 반환. Google Fonts API Korean subset 기반.
    Lambda 인스턴스 레벨 메모리 캐시 (TTL=인스턴스 수명 ≒ 24h).

    응답: { status: "success", fonts: [{ family, category, slug }, ...] }
    """
    try:
        fonts = get_korean_fonts()
        return {"status": "success", "fonts": fonts}
    except Exception as e:
        print(f"[get_fonts 에러] {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=503,
            detail="폰트 목록을 불러올 수 없습니다. 잠시 후 다시 시도해주세요.",
        )


@router.get("/subtitle-settings")
def get_subtitle_settings_endpoint(user=Depends(require_active_subscription)):
    """
    GET /api/blog/subtitle-settings

    select step 진입 시 저장된 자막 스타일 설정 로드.
    저장값 없으면 settings=null 반환 (FE 가 기본값으로 처리).

    응답: { status: "success", settings: { title: {...}, subtitle: {...} } | null }
    """
    user_id = user["id"]
    try:
        settings = get_subtitle_settings(user_id)
        return {"status": "success", "settings": settings}
    except Exception as e:
        print(f"[get_subtitle_settings 에러] user={user_id} {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="설정을 불러올 수 없습니다.")


@router.put("/subtitle-settings")
def put_subtitle_settings_endpoint(
    req: SubtitleSettingsRequest,
    user=Depends(require_active_subscription),
):
    """
    PUT /api/blog/subtitle-settings

    사용자가 폰트/크기/색상을 변경할 때 계정에 저장 (FE debounce 500ms 후 호출).
    font_family 는 GET /api/blog/fonts 응답 기반 허용 목록으로 검증.

    응답: { status: "success" } 또는 422 에러
    """
    user_id = user["id"]
    settings_dict = req.model_dump()

    # font_family 유효성 검증 (허용 목록 = Google Fonts Korean subset)
    try:
        allowed_families = get_allowed_font_families()
    except Exception:
        # Google Fonts API 장애 시 유효성 검증 완화 (저장은 허용)
        allowed_families = set()
        print(f"[put_subtitle_settings] font 허용 목록 로드 실패 — 검증 완화")

    errors = validate_subtitle_settings(settings_dict, allowed_families)
    if errors:
        raise HTTPException(
            status_code=422,
            detail="유효하지 않은 설정값입니다.: " + " | ".join(errors),
        )

    try:
        success = save_subtitle_settings(user_id, settings_dict)
        if not success:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[put_subtitle_settings 에러] user={user_id} {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="설정을 저장할 수 없습니다.")
