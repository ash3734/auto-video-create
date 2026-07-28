import os
import requests
import json
import time
from dotenv import load_dotenv
from .account_service import check_user_credits, deduct_credits, get_current_credits
from .concept_samples import get_template_id

load_dotenv()

CREATOMATE_API_KEY = os.environ["CREATOMATE_API_KEY"]

# sprint-4 (B-2): 모듈 레벨 CREATOMATE_TEMPLATE_ID(단일, 폐기된 기존 프로덕션 템플릿) 상수는
# 완전히 제거됐다 — 더 이상 어떤 샘플도 이 ID 를 참조하지 않는다(data-model.md §3).
# template_id 는 이제 concept_sample_id 기준으로 concept_samples.get_template_id() 룩업.

## 네이버 "e78f211a-9e4c-4f5c-a871-36b9d680ee11"
## 유튜브 "14457245-7822-48a6-a711-62d15b739b85"

def create_creatomate_video(
    audio_paths,
    scripts,
    concept_sample_id=None,
    title=None,
    output_path="creatomate_result.mp4",
    user_id=None,
    **kwargs,
):
    print("create_creatomate_video 호출")

    # 크레딧 체크 (1000 크레딧 필요)
    if user_id:
        if not check_user_credits(user_id, 1000):
            current_credits = get_current_credits(user_id)  # 현재 크레딧 조회
            return {
                "error": "insufficient_credits",
                "message": f"크레딧이 부족합니다. 현재 보유 크레딧: {current_credits}개, 필요 크레딧: 1000개",
                "current_credits": current_credits,
                "required_credits": 1000
            }

    # sprint-4 (B-2, architecture.md §4-2): concept_sample_id → template_id 룩업.
    # placeholder(None) 상태면 Creatomate 를 호출하지 않고 명확한 에러로 안내(방어적 설계) —
    # "확보 전엔 죽는" 게 아니라 "확보 전엔 안내 메시지로 막는다".
    template_id = get_template_id(concept_sample_id, env=os.environ.get("ENV"))
    if not template_id:
        return {
            "error": "concept_sample_template_not_configured",
            "message": "선택한 컨셉의 템플릿이 아직 준비되지 않았어요. 다른 컨셉을 선택해 주세요.",
        }

    # sprint-4 (B-2): audio1~audio5 하드코딩 dict 리터럴 → N(=len(audio_paths)) 가변 처리.
    scene_count = len(audio_paths)
    variables = {f"audio{i + 1}.source": audio_paths[i] for i in range(scene_count)}
    if title:
        variables["title.text"] = title
    variables.update(kwargs)
    payload = {
        "template_id": template_id,
        "modifications": variables
    }
    
    try:
        response = requests.post(
            "https://api.creatomate.com/v1/renders",
            headers={
                "Authorization": f"Bearer {CREATOMATE_API_KEY}",
                "Content-Type": "application/json"
            },
            data=json.dumps(payload)
        )
        
        result = response.json()
        
        # 성공 시 크레딧 차감
        if user_id and response.status_code == 200:
            # render_id가 있는지 확인 (성공적인 렌더링 시작)
            if isinstance(result, list) and result and result[0].get('id'):
                render_id = result[0]['id']
                deduct_success = deduct_credits(user_id, 1000, "video_generation")
                if deduct_success:
                    print(f"[+] {user_id} 크레딧 차감 완료 (render_id: {render_id})")
                else:
                    print(f"[!] {user_id} 크레딧 차감 실패")
            elif isinstance(result, dict) and result.get('id'):
                render_id = result['id']
                deduct_success = deduct_credits(user_id, 1000, "video_generation")
                if deduct_success:
                    print(f"[+] {user_id} 크레딧 차감 완료 (render_id: {render_id})")
                else:
                    print(f"[!] {user_id} 크레딧 차감 실패")
        
        return result
        
    except Exception as e:
        print(f"[!] Creatomate API 호출 실패: {e}")
        return {
            "error": "api_error",
            "message": f"영상 생성 API 호출 실패: {str(e)}"
        }

def get_creatomate_vars(durations, scene_count):
    """scene_count(N) 기반 composition_1~N + composition_title/logo 타이밍 계산.

    sprint-4 (B-2, architecture.md §4-3/data-model.md §4): N-일반화. 현재 /api/blog/generate-video
    라이브 경로에서는 호출되지 않는다(F-2 — 기존 단일 템플릿이 Creatomate 자동 타이밍에 의존).
    신규 템플릿 4종이 자동 타이밍을 지원하지 않을 경우에만 연결 검토 대상(DEP-S4-01/06 실사 후 판단).
    호출부(scripts/pipeline_blog_to_shorts.py, 오프라인 전용)는 시그니처 변경으로 별도 갱신 필요.
    """
    print("get_creatomate_vars 호출")
    creatomate_vars = {}
    for i in range(scene_count):
        creatomate_vars[f"composition_{i+1}.duration"] = durations[i] if i < len(durations) and durations[i] is not None else 0
    times = [0]
    for i in range(1, scene_count):
        prev_time = times[-1] + (durations[i-1] if i-1 < len(durations) and durations[i-1] is not None else 0)
        times.append(prev_time)
    for i in range(scene_count):
        creatomate_vars[f"composition_{i+1}.time"] = times[i]
    last_time = creatomate_vars[f"composition_{scene_count}.time"]
    last_duration = creatomate_vars[f"composition_{scene_count}.duration"]
    total_duration = last_time + last_duration
    creatomate_vars["composition_title.time"] = 0
    creatomate_vars["composition_title.duration"] = total_duration
    creatomate_vars["composition_logo.time"] = 0
    creatomate_vars["composition_logo.duration"] = total_duration
    creatomate_vars["duration"] = total_duration
    return creatomate_vars

def poll_creatomate_video_url(render_id, api_key=None, max_poll=150, poll_interval=2):
    print("poll_creatomate_video_url 호출")
    """
    Creatomate render_id를 받아 최종 영상 URL을 폴링해서 반환한다.
    성공 시 URL(str), 실패 시 None 반환
    """
    import requests
    import os
    api_key = api_key or os.environ.get('CREATOMATE_API_KEY')
    video_url = None
    for i in range(max_poll):
        poll_resp = requests.get(
            f"https://api.creatomate.com/v1/renders/{render_id}",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        poll_json = poll_resp.json()
        status = poll_json.get('status')
        url_in_result = poll_json.get('result', {}).get('url') if poll_json.get('result') else None
        url_top_level = poll_json.get('url')
        if (status in ['completed', 'succeeded']) and (url_in_result or url_top_level):
            video_url = url_in_result or url_top_level
            break
        elif status == 'failed':
            return None
        time.sleep(poll_interval)
    return video_url
