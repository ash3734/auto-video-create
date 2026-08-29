from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from services.blog_shorts import extract_blog_content, get_blog_media_and_scripts
from services.summarize import summarize_for_shorts_sets
from services.tts_typecast import (
    tts_with_typecast_multi,
    TypecastError,
)
from services.create_creatomate_video import create_creatomate_video, get_creatomate_vars, poll_creatomate_video_url
from services.account_service import get_user_if_active, check_user_credits, get_current_credits
from services.ai_background import generate_backgrounds_parallel, FALLBACK_URL as DEFAULT_BG_FALLBACK_URL
from services.image_mirror import maybe_mirror
from services.alerting import alert
# cycle-3: 자막 스타일 편집 신규 서비스
from services.font_service import get_korean_fonts, get_allowed_font_families
from services.subtitle_settings_service import (
    get_subtitle_settings,
    save_subtitle_settings,
    validate_subtitle_settings,
    validate_text_style,
    apply_subtitle_settings_to_variables,
    # feat/style-templates: 이름 붙인 템플릿 CRUD (최대 5개)
    get_subtitle_templates,
    create_subtitle_template,
    update_subtitle_template,
    delete_subtitle_template,
    TemplateLimitReachedError,
    TemplateNotFoundError,
    LastTemplateError,
)
from services.scene_counts import (
    normalize_scene_count,
    get_subtitle_suffixes,
    available_scene_counts,
    DEFAULT_SCENE_COUNT,
)
from services.speeds import available_speeds, normalize_speed, to_tempo
from services.voices import available_voices, normalize_voice_id
from services.voice_preview import get_preview_url
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


def _safe_host(url) -> str:
    """알림에 남길 블로그 호스트만 뽑는다.

    URL 전체를 남기면 유저가 어떤 글을 봤는지가 로그에 쌓인다. 진단에 필요한 건
    "어느 플랫폼 파서가 깨졌나"뿐이므로 호스트만 남긴다.
    """
    try:
        return urlparse(str(url)).netloc or "(unknown)"
    except Exception:
        return "(unparsable)"


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
    # 장면 수 선택 (4~8). 미전송/무효 시 기본 5 — 기존 동작 유지.
    scene_count: Optional[int] = None

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


@router.get("/scene-counts")
def get_scene_counts():
    """GET /api/blog/scene-counts

    선택 가능한 장면 수 목록. available=false 면 템플릿 미등록(선택 불가).

    응답: {"scene_counts": [{"scene_count": 4, "available": false, "is_default": false}, ...],
           "default_scene_count": 5}
    """
    return {
        "scene_counts": available_scene_counts(),
        "default_scene_count": DEFAULT_SCENE_COUNT,
    }

@router.get("/speeds")
def get_speeds():
    """GET /api/blog/speeds

    선택 가능한 나레이션 배속 목록. is_default=true 가 현재 기본 배속(1배)이다.
    값은 **상대 배속**이라 1.0 이 지금까지의 속도와 같다.
    """
    return {"speeds": available_speeds()}


@router.get("/voices")
def get_voices():
    """GET /api/blog/voices

    선택 가능한 나레이션 음성 목록. is_default=true 가 현재 기본 음성이다.
    """
    return {"voices": available_voices()}


class VoicePreviewRequest(BaseModel):
    voice_id: str
    # 유저가 화면에서 보고 있는 실제 스크립트. 제네릭 샘플이 아니라 이걸 읽힌다.
    text: str
    # 배속. 미리듣기가 실제 결과물과 같은 속도로 들려야 고르는 의미가 있다.
    speed: Optional[float] = None


@router.post("/voice-preview")
def voice_preview(req: VoicePreviewRequest, user=Depends(require_active_subscription)):
    """POST /api/blog/voice-preview

    (voice_id, text) 조합의 미리듣기 mp3 URL 을 돌려준다. 같은 조합이면 S3 캐시를
    그대로 쓰므로 재생성 비용이 없다.

    크레딧을 차감하지 않는다 — 미리듣기는 한 줄이라 영상 한 편의 1/5 비용이고,
    여기에 과금하면 기능을 쓰지 않게 되어 존재 이유가 사라진다.
    """
    api_key = os.environ.get("TYPECAST_API_KEY")
    result = get_preview_url(req.voice_id, req.text, api_key, speed=req.speed)
    if result.get("status") != "success":
        # 200 으로 돌려준다 — 미리듣기 실패는 화면을 막을 사안이 아니고,
        # FE 는 해당 행에만 에러를 표시하고 선택은 계속 가능해야 한다.
        return result
    return result


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

        result = get_blog_media_and_scripts(
            req.blog_url, scene_count=normalize_scene_count(req.scene_count)
        )
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
        # 여기 오는 건 **우리가 예상하지 못한 실패**다. 유저 탓인 경우(비지원 플랫폼,
        # 미등록 블로그)는 위에서 이미 갈라져 나갔다.
        #
        # 이 catch-all 이 조용했던 탓에 네이버가 마크업을 바꿔 파서가 깨져도 우리는 알 수
        # 없었고, 유저에게는 "다른 글로 시도해주세요"라고 유저 탓처럼 안내됐다.
        # 모르는 실패는 일단 알린다 — 시끄러우면 그때 유형별로 내리면 된다.
        # (특정 예외가 유저 탓 소음으로 판명되면 위에 별도 except 로 분리할 것)
        print("extract_all 에러:", e)
        traceback.print_exc()
        alert(
            "extract_all",
            f"예상치 못한 추출 실패: {e}",
            error_type=type(e).__name__,
            blog_host=_safe_host(req.blog_url),
        )
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


# feat/style-templates: 이름 붙인 템플릿(최대 5개) 요청 모델
class SubtitleTemplateCreateRequest(BaseModel):
    name: str
    title: TextStyleModel
    subtitle: TextStyleModel


class SubtitleTemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    title: Optional[TextStyleModel] = None
    subtitle: Optional[TextStyleModel] = None


# --- 최종 영상 생성 API ---
class GenerateVideoRequest(BaseModel):
    title: str
    scripts: List[str]
    sections: List[SectionMedia]  # scene_count 개 (기본 5)
    # cycle-3: optional — 없으면 Creatomate 템플릿 기본값 유지
    subtitle_settings: Optional[SubtitleSettingsModel] = None
    # 장면 수 선택 (4~8). 미전송 시 scripts 길이에서 추론, 그것도 무효면 기본 5.
    scene_count: Optional[int] = None
    # 나레이션 음성. 미전송/무효 시 기본값(혜리) — 기존 유저 결과물이 바뀌지 않는다.
    voice_id: Optional[str] = None
    # 나레이션 배속(상대값, 1.0 = 지금 속도). 미전송/무효 시 1.0 — 기존 결과물 유지.
    speed: Optional[float] = None

class GenerateVideoResponse(BaseModel):
    status: str
    video_url: Optional[str] = None
    message: Optional[str] = None

@router.post("/generate-video")
def generate_video(req: GenerateVideoRequest, user=Depends(require_active_subscription_and_credits)):
    # user_id 를 함께 남긴다 — 일일 사용량 리포트가 "유저별 **시도** 횟수"를 로그에서
    # 세기 때문이다. S3 크레딧 이력은 성공한 건만 남으므로, 실패한 시도(이탈로 이어지는
    # 그 지점)는 이 로그로만 알 수 있다. 형식을 바꾸면 리포트 집계가 조용히 깨진다.
    print(f"generate_video 호출 user_id={user.get('id')}")
    try:
        # 장면 수: 명시값 우선, 없으면 scripts 길이에서 추론 (무효 시 기본 5)
        scene_count = normalize_scene_count(
            req.scene_count if req.scene_count is not None else len(req.scripts)
        )

        # 1. TTS 변환 (scripts → mp3 url) — 2026-08-05 Supertone → Typecast 전환
        TYPECAST_API_KEY = os.environ.get("TYPECAST_API_KEY")
        # 2026-08-17: 음성 선택 도입. 요청값을 그대로 믿지 않고 허용 목록으로 정규화한다
        # — 임의의 voice_id 로 엉뚱한(영어 등) 음성 영상이 나가면 1,000크레딧이 날아간다.
        # 미전송/무효면 기본값(혜리)이라 기존 유저의 결과물은 그대로다.
        TYPECAST_VOICE_ID = normalize_voice_id(req.voice_id)
        # 배속 선택 (2026-08-29). 요청값을 그대로 믿지 않고 허용 목록으로 정규화한다
        # — 임의의 속도로 엉뚱한 길이의 영상이 나가면 1,000크레딧이 날아간다.
        # 미전송/무효면 1.0 배(= tempo 1.4)라 기존 유저의 결과물은 그대로다.
        TTS_SPEED = to_tempo(req.speed)
        # "영상이 너무 빠르다/느리다" 문의가 오면 어느 배속으로 만든 건지 알아야 한다.
        print(f"나레이션 배속 {normalize_speed(req.speed)}배 (tempo={TTS_SPEED})")
        audio_local_paths, audio_urls = tts_with_typecast_multi(
            req.scripts,
            api_key=TYPECAST_API_KEY,
            voice_id=TYPECAST_VOICE_ID,
            speed=TTS_SPEED,
        )
        audio_local_paths = audio_local_paths[:scene_count]
        audio_urls = audio_urls[:scene_count]

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
                get_subtitle_suffixes(scene_count),
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
            scene_count=scene_count,
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
            # 어떤 응답이 왔는지 남긴다 — 이게 없어서 원인 파악이 불가능했다 (2026-08-06)
            print(f"[generate_video] Creatomate 응답에 render_id 없음: {str(result)[:500]}")
            return {
                "status": "error",
                "error_code": "creatomate_no_render_id",
                "message": "Creatomate 응답에 렌더링 ID가 없습니다.",
                "error_type": "creatomate_no_render_id",
            }

        poll_url = f"https://api.creatomate.com/v1/renders/{render_id}"
        return {"status": "started", "render_id": render_id, "poll_url": poll_url}
    except TypecastError as e:
        # 음성 생성 실패 — 사용자에게 보여줄 수 있는 메시지를 그대로 전달.
        # (API 키 잔액 소진/한도 초과 등이 여기로 온다)
        print("[generate_video] TTS 실패:", e)
        return {
            "status": "error",
            "error_code": "tts_failed",
            "message": f"음성을 만들지 못했어요. {e}",
            "error_type": "tts_failed",
        }
    except Exception as e:
        # TypecastError 는 위에서 갈라져 나갔다. 여기 오는 건 전부 예상 밖이다 —
        # Creatomate 응답 파싱, S3 업로드, 자막 설정 조회 등 어디서든 터질 수 있고,
        # 지금까지는 그 어떤 것도 알림 없이 사라졌다.
        print("[generate_video 에러]", e)
        traceback.print_exc()
        # scene_count 는 try 블록 첫 줄에서 할당되므로 그 줄이 터지면 미정의다.
        # 알림 코드가 NameError 로 2차 사고를 내면 알림 자체를 잃는다 — 항상 존재하는
        # 요청 값을 쓴다.
        alert(
            "generate_video",
            f"예상치 못한 영상 생성 실패: {e}",
            error_type=type(e).__name__,
            requested_scene_count=getattr(req, "scene_count", None),
        )
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


# ─────────────────────────────────────────────
# feat/style-templates 신규 엔드포인트
#
# 계정당 단일 subtitle_settings 를 대체하는 것이 아니라, 이름 붙인 템플릿
# 최대 5개(subtitle_templates)를 저장/재사용할 수 있게 하는 편의 계층.
# generate-video 는 변경 없음 — FE 가 선택한 템플릿의 {title, subtitle} 을
# 그대로 subtitle_settings 로 보낸다.
#
# 기존 GET/PUT /subtitle-settings 엔드포인트는 하위 호환을 위해 그대로 유지한다
# (제거하지 않음). 신규 FE 는 아래 CRUD 를 사용한다.
# ─────────────────────────────────────────────

@router.get("/subtitle-templates")
def get_subtitle_templates_endpoint(user=Depends(require_active_subscription)):
    """
    GET /api/blog/subtitle-templates

    이름 붙인 자막 스타일 템플릿 목록 조회 (계정당 최대 5개).
    레거시 단일 subtitle_settings 만 있는 계정은 자동 마이그레이션되어
    [{id, name:"템플릿 1", title, subtitle}] 형태로 반환된다(영속화는 다음
    저장/수정/삭제 시점에 lazy 하게 이뤄짐 — 조회만으로는 S3 에 쓰지 않음).

    응답: { "templates": [{id, name, title, subtitle}, ...] }
    """
    user_id = user["id"]
    try:
        templates = get_subtitle_templates(user_id)
        return {"templates": templates}
    except Exception as e:
        print(f"[get_subtitle_templates 에러] user={user_id} {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="템플릿 목록을 불러올 수 없습니다.")


@router.post("/subtitle-templates")
def create_subtitle_template_endpoint(
    req: SubtitleTemplateCreateRequest,
    user=Depends(require_active_subscription),
):
    """
    POST /api/blog/subtitle-templates

    신규 이름 붙인 자막 스타일 템플릿 생성. 계정당 최대 5개.
    이미 5개면 400 + {"error_code": "template_limit_reached"}.
    스타일 검증 실패 시 400 + 메시지.

    응답(성공): 생성된 템플릿 {id, name, title, subtitle}
    """
    user_id = user["id"]

    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="템플릿 이름은 비어있을 수 없습니다.")

    style_dict = {"title": req.title.model_dump(), "subtitle": req.subtitle.model_dump()}

    try:
        allowed_families = get_allowed_font_families()
    except Exception:
        allowed_families = set()
        print("[create_subtitle_template] font 허용 목록 로드 실패 — 검증 완화")

    errors = validate_subtitle_settings(style_dict, allowed_families)
    if errors:
        raise HTTPException(
            status_code=400,
            detail="유효하지 않은 설정값입니다.: " + " | ".join(errors),
        )

    try:
        template = create_subtitle_template(
            user_id, req.name.strip(), style_dict["title"], style_dict["subtitle"]
        )
        return template
    except TemplateLimitReachedError:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "template_limit_reached",
                "message": "템플릿은 최대 5개까지 저장할 수 있습니다.",
            },
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[create_subtitle_template 에러] user={user_id} {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="템플릿을 생성할 수 없습니다.")


@router.put("/subtitle-templates/{template_id}")
def update_subtitle_template_endpoint(
    template_id: str,
    req: SubtitleTemplateUpdateRequest,
    user=Depends(require_active_subscription),
):
    """
    PUT /api/blog/subtitle-templates/{template_id}

    기존 템플릿 부분 수정 — name/title/subtitle 중 요청에 포함된(None 이 아닌)
    필드만 반영. 없는 template_id 면 404. 검증 실패 시 400.

    응답(성공): 수정된 템플릿 {id, name, title, subtitle}
    """
    user_id = user["id"]

    if req.name is not None and not req.name.strip():
        raise HTTPException(status_code=400, detail="템플릿 이름은 비어있을 수 없습니다.")

    title_dict = req.title.model_dump() if req.title is not None else None
    subtitle_dict = req.subtitle.model_dump() if req.subtitle is not None else None

    if title_dict is not None or subtitle_dict is not None:
        try:
            allowed_families = get_allowed_font_families()
        except Exception:
            allowed_families = set()
            print("[update_subtitle_template] font 허용 목록 로드 실패 — 검증 완화")

        errors: List[str] = []
        if title_dict is not None:
            errors.extend(f"[title] {e}" for e in validate_text_style(title_dict, allowed_families))
        if subtitle_dict is not None:
            errors.extend(f"[subtitle] {e}" for e in validate_text_style(subtitle_dict, allowed_families))

        if errors:
            raise HTTPException(
                status_code=400,
                detail="유효하지 않은 설정값입니다.: " + " | ".join(errors),
            )

    try:
        template = update_subtitle_template(
            user_id,
            template_id,
            name=req.name.strip() if req.name is not None else None,
            title=title_dict,
            subtitle=subtitle_dict,
        )
        return template
    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")
    except LookupError:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[update_subtitle_template 에러] user={user_id} {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="템플릿을 수정할 수 없습니다.")


@router.delete("/subtitle-templates/{template_id}")
def delete_subtitle_template_endpoint(
    template_id: str,
    user=Depends(require_active_subscription),
):
    """
    DELETE /api/blog/subtitle-templates/{template_id}

    템플릿 삭제. 없으면 404.

    응답(성공): { "status": "success" }
    """
    user_id = user["id"]
    try:
        delete_subtitle_template(user_id, template_id)
        return {"status": "success"}
    except LastTemplateError:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "cannot_delete_last_template",
                "message": "마지막 템플릿은 삭제할 수 없어요.",
            },
        )
    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")
    except LookupError:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[delete_subtitle_template 에러] user={user_id} {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="템플릿을 삭제할 수 없습니다.")
