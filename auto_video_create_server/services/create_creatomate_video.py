import os
import requests
import json
import time
from dotenv import load_dotenv
from .account_service import check_user_credits, deduct_credits, get_current_credits
from .alerting import alert
from .scene_counts import get_template_id, normalize_scene_count

load_dotenv()

CREATOMATE_API_KEY = os.environ["CREATOMATE_API_KEY"]

# 장면 수별 템플릿 ID 는 services/scene_counts.py 에서 관리한다 (ENV 분기 포함).
# 하위호환: 기존 코드가 참조하던 모듈 상수는 기본 장면 수(5) 기준으로 유지.
CREATOMATE_TEMPLATE_ID = get_template_id(5)

## 네이버 "e78f211a-9e4c-4f5c-a871-36b9d680ee11"
## 유튜브 "14457245-7822-48a6-a711-62d15b739b85"

def create_creatomate_video(audio_paths, scripts, title=None, output_path="creatomate_result.mp4", video5=None, user_id=None, scene_count=5, **kwargs):
    print("create_creatomate_video 호출")

    scene_count = normalize_scene_count(scene_count)
    template_id = get_template_id(scene_count)
    if not template_id:
        # 해당 장면 수의 Creatomate 템플릿이 아직 등록되지 않음 — 크래시 대신 안전한 에러 응답
        alert("config", "장면 수 템플릿 미등록", scene_count=scene_count)
        return {
            "error": "scene_count_template_not_configured",
            "message": f"{scene_count}장면 템플릿이 아직 준비되지 않았어요. 다른 장면 수로 시도해주세요.",
        }

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

    # 오디오는 장면 수(N)만큼 주입 — 기존 고정 5개 딕셔너리 대체
    variables = {}
    for i in range(scene_count):
        if i < len(audio_paths):
            variables[f"audio{i + 1}.source"] = audio_paths[i]
    if video5:
        variables["video5.source"] = video5
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
            data=json.dumps(payload),
            # 타임아웃이 없으면 Creatomate 가 응답을 안 줄 때 Lambda 30초 예산을 통째로 날린다.
            timeout=(5, 20),
        )

        try:
            result = response.json()
        except ValueError:
            result = None

        # 진단 로그: 상태 코드 + 응답 본문 요약.
        # 이게 없어서 "렌더링 ID가 없습니다" 만 뜨고 원인을 알 수 없었다 (2026-08-06).
        # Authorization 헤더는 절대 로그에 남기지 않는다.
        print(
            f"[create_creatomate_video] template_id={template_id} "
            f"status={response.status_code} body={str(result)[:500] if result is not None else (response.text or '')[:500]}"
        )

        if response.status_code >= 400:
            # Creatomate 는 에러를 message/hint 등 다양한 키로 준다 — 있는 대로 뽑아 올린다.
            detail = ""
            if isinstance(result, dict):
                detail = (
                    result.get("message")
                    or result.get("hint")
                    or result.get("error")
                    or ""
                )
            if not detail:
                detail = (response.text or "")[:200]
            # 설정 불일치(존재하지 않는 템플릿 ID)와 API 장애를 구분해 알린다.
            # 2026-08-08: test 5장면 템플릿이 Creatomate 에서 삭제됐는데 나흘간 아무도 몰랐다.
            source = "config" if response.status_code == 400 else "creatomate"
            alert(
                source,
                f"렌더 요청 실패 status={response.status_code} detail={detail}",
                template_id=template_id,
                scene_count=scene_count,
            )
            return {
                "error": "creatomate_error",
                "message": f"Creatomate {response.status_code}: {detail}".strip(),
            }

        # 성공 시 크레딧 차감
        if user_id and response.status_code == 200:
            # render_id가 있는지 확인 (성공적인 렌더링 시작)
            if isinstance(result, list) and result and result[0].get('id'):
                render_id = result[0]['id']
                deduct_success = deduct_credits(user_id, 1000, "video_generation")
                if deduct_success:
                    print(f"[+] {user_id} 크레딧 차감 완료 (render_id: {render_id})")
                else:
                    # 렌더는 시작됐는데 차감이 안 된 상태 — 돈이 새므로 반드시 알린다.
                    alert("credits", "렌더 시작 후 크레딧 차감 실패", user_id=user_id, render_id=render_id)
            elif isinstance(result, dict) and result.get('id'):
                render_id = result['id']
                deduct_success = deduct_credits(user_id, 1000, "video_generation")
                if deduct_success:
                    print(f"[+] {user_id} 크레딧 차감 완료 (render_id: {render_id})")
                else:
                    # 렌더는 시작됐는데 차감이 안 된 상태 — 돈이 새므로 반드시 알린다.
                    alert("credits", "렌더 시작 후 크레딧 차감 실패", user_id=user_id, render_id=render_id)
        
        return result
        
    except Exception as e:
        alert("creatomate", f"API 호출 예외: {e}", template_id=template_id)
        return {
            "error": "api_error",
            "message": f"영상 생성 API 호출 실패: {str(e)}"
        }

def get_creatomate_vars(durations):
    print("get_creatomate_vars 호출")
    creatomate_vars = {}
    for i in range(5):
        creatomate_vars[f"composition_{i+1}.duration"] = durations[i] if i < len(durations) and durations[i] is not None else 0
    times = [0]
    for i in range(1, 5):
        prev_time = times[-1] + (durations[i-1] if i-1 < len(durations) and durations[i-1] is not None else 0)
        times.append(prev_time)
    for i in range(5):
        creatomate_vars[f"composition_{i+1}.time"] = times[i]
    comp5_time = creatomate_vars["composition_5.time"]
    comp5_duration = creatomate_vars["composition_5.duration"]
    total_duration = comp5_time + comp5_duration
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
