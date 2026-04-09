import os
import requests
import json
import time
from dotenv import load_dotenv
from .account_service import check_user_credits, deduct_credits, get_current_credits

load_dotenv()

CREATOMATE_API_KEY = os.environ["CREATOMATE_API_KEY"]
if os.environ.get("ENV") == "production":
    CREATOMATE_TEMPLATE_ID = "cab85e50-1e78-41b8-9644-80a061d349f6"
else:
    CREATOMATE_TEMPLATE_ID = "eda9d421-b086-4660-9f3c-9236d826226f"

## 네이버 "e78f211a-9e4c-4f5c-a871-36b9d680ee11"
## 유튜브 "14457245-7822-48a6-a711-62d15b739b85"

def create_creatomate_video(audio_paths, scripts, title=None, output_path="creatomate_result.mp4", video5=None, user_id=None, **kwargs):
    print("[create_creatomate_video] 호출")
    print(
        "[create_creatomate_video] 입력 요약 | "
        f"user_id={user_id}, audio_count={len(audio_paths) if audio_paths else 0}, "
        f"script_count={len(scripts) if scripts else 0}, "
        f"title_exists={bool(title)}, extra_var_count={len(kwargs)}"
    )
    
    # 크레딧 체크 (1000 크레딧 필요)
    if user_id:
        print(f"[create_creatomate_video] 크레딧 검사 시작 | user_id={user_id}, required=1000")
        if not check_user_credits(user_id, 1000):
            current_credits = get_current_credits(user_id)  # 현재 크레딧 조회
            print(
                "[create_creatomate_video] 크레딧 부족으로 종료 | "
                f"user_id={user_id}, current_credits={current_credits}"
            )
            return {
                "error": "insufficient_credits",
                "message": f"크레딧이 부족합니다. 현재 보유 크레딧: {current_credits}개, 필요 크레딧: 1000개",
                "current_credits": current_credits,
                "required_credits": 1000
            }
        print(f"[create_creatomate_video] 크레딧 검사 통과 | user_id={user_id}")
    
    variables = {
        "audio1.source": audio_paths[0],
        "audio2.source": audio_paths[1],
        "audio3.source": audio_paths[2],
        "audio4.source": audio_paths[3],
        "audio5.source": audio_paths[4],
    }
    if video5:
        variables["video5.source"] = video5
    if title:
        variables["title.text"] = title
    variables.update(kwargs)
    payload = {
        "template_id": CREATOMATE_TEMPLATE_ID,
        "modifications": variables
    }
    print(
        "[create_creatomate_video] payload 준비 완료 | "
        f"template_id={CREATOMATE_TEMPLATE_ID}, modification_count={len(variables)}"
    )
    
    try:
        print("[create_creatomate_video] Creatomate API 요청 시작")
        response = requests.post(
            "https://api.creatomate.com/v1/renders",
            headers={
                "Authorization": f"Bearer {CREATOMATE_API_KEY}",
                "Content-Type": "application/json"
            },
            data=json.dumps(payload)
        )
        print(
            "[create_creatomate_video] Creatomate API 응답 수신 | "
            f"status_code={response.status_code}"
        )
        
        result = response.json()
        if isinstance(result, list):
            preview_id = result[0].get("id") if result and isinstance(result[0], dict) else None
            print(
                "[create_creatomate_video] 응답 파싱 완료 | "
                f"type=list, length={len(result)}, first_id={preview_id}"
            )
        elif isinstance(result, dict):
            print(
                "[create_creatomate_video] 응답 파싱 완료 | "
                f"type=dict, keys={list(result.keys())[:10]}, id={result.get('id')}"
            )
        else:
            print(f"[create_creatomate_video] 응답 파싱 완료 | type={type(result)}")
        
        # 성공 시 크레딧 차감
        if user_id and response.status_code == 200:
            print(f"[create_creatomate_video] 크레딧 차감 시도 | user_id={user_id}, amount=1000")
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
            else:
                print("[create_creatomate_video] 크레딧 차감 스킵 | render_id 미확인")
        elif user_id:
            print(
                "[create_creatomate_video] 크레딧 차감 스킵 | "
                f"user_id={user_id}, status_code={response.status_code}"
            )
        
        print("[create_creatomate_video] 정상 반환")
        return result
        
    except Exception as e:
        print(f"[create_creatomate_video][ERROR] Creatomate API 호출 실패: {e}")
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
