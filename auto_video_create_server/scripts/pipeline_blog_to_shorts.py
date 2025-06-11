import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.naver import extract_blog_content, select_videos_by_url
from services.summarize import summarize_for_shorts_sets
from services.tts_supertone import tts_with_supertone_multi
from services.create_creatomate_video import create_creatomate_video, get_creatomate_vars
import wave
import contextlib
import mutagen
from mutagen.mp3 import MP3

def select_image_for_script(script_idx, script_text, images):
    print("\n------------------------------")
    print(f"[스크립트 {script_idx+1}]\n{script_text}")
    print("------------------------------")
    while True:
        selected = input(f"이 스크립트에 사용할 이미지 번호를 입력하세요 (1~{len(images)}): ")
        try:
            idx = int(selected)
            if 1 <= idx <= len(images):
                return images[idx-1]
            else:
                print("잘못된 번호입니다. 다시 입력하세요.")
        except Exception:
            print("숫자를 입력하세요.")

if __name__ == "__main__":
    url = input("네이버 블로그 주소를 입력하세요: ")
    text, images, videos = extract_blog_content(url)

    title, scripts = summarize_for_shorts_sets(text)

    print(f"\n[쇼츠 제목] {title}")
    print("[쇼츠 스크립트]")
    for i, s in enumerate(scripts, 1):
        print(f"{i}: {s['script'] if isinstance(s, dict) else s}")

    selected_images = []
    script_texts = []
    script_texts = [s['script'] if isinstance(s, dict) else s for s in scripts[:4]]
    for idx, script_text in enumerate(script_texts):
        img = select_image_for_script(idx, script_text, images)
        selected_images.append(img)

    # 영상 선택 (선택적)
    selected_video = None
    if videos:
        selected_videos = select_videos_by_url(videos)
        if selected_videos:
            selected_video = selected_videos[0]

    # TTS 변환 (Supertone)
    print("\n[TTS 변환 진행 중...")
    SUPERTONE_API_KEY = "e18c81dbf99dc1fabb8084caebb971d2"
    SUPERTONE_VOICE_ID = "42b52760fe9ecf701f8ed3"
    SUPERTONE_SPEED = 1.4
    audio_local_paths, audio_urls = tts_with_supertone_multi(
        scripts,
        api_key=SUPERTONE_API_KEY,
        voice_id=SUPERTONE_VOICE_ID,
        speed=SUPERTONE_SPEED
    )
    if len(audio_local_paths) < 5:
        print("TTS 음성 파일이 5개 미만입니다. 스크립트 또는 TTS 오류를 확인하세요.")
        sys.exit(1)
    audio_local_paths = audio_local_paths[:5]
    audio_urls = audio_urls[:5]

    # 각 mp3 파일의 길이(초) 추출
    durations = []
    for path in audio_local_paths:
        audio = MP3(path)
        durations.append(audio.info.length)
    # Creatomate에 넘길 변수 dict 계산 (서비스 함수 사용)
    creatomate_vars = get_creatomate_vars(durations)
    print("\n[Creatomate에 넘길 duration, time 변수]", creatomate_vars)

    # 동영상 생성
    print("\n[동영상 생성 진행 중...")
    result = create_creatomate_video(
        image_urls=selected_images,
        audio_paths=audio_urls,  # S3 public URL 리스트로 전달
        scripts=[s['script'] if isinstance(s, dict) else s for s in scripts],
        title=title,
        video5=selected_video,
        **creatomate_vars
    )
    print("\n[Creatomate API 응답]")
    print(result)
    print("\n파이프라인 완료!")

    # Creatomate 렌더링 결과에서 동영상 URL 추출 및 로컬 저장
    try:
        # result가 list면 첫 번째 요소 사용(혹은 에러 처리)
        if isinstance(result, list):
            print("[경고] Creatomate 응답이 list입니다. 첫 번째 요소를 사용합니다.")
            result = result[0] if result else {}
        if not isinstance(result, dict):
            print("[오류] Creatomate 응답이 dict가 아닙니다. 전체 응답:", result)
            sys.exit(1)
        render_id = result.get('id')
        if not render_id:
            print("[오류] Creatomate 응답에 렌더링 ID가 없습니다.")
            sys.exit(1)
        import time
        import requests
        video_url = None
        for i in range(150):  # 최대 150회(약 5분) 폴링
            poll_resp = requests.get(
                f"https://api.creatomate.com/v1/renders/{render_id}",
                headers={"Authorization": f"Bearer {os.environ['CREATOMATE_API_KEY']}"}
            )
            poll_json = poll_resp.json()
            status = poll_json.get('status')
            print(f"[폴링 {i+1}/150] Creatomate 렌더링 상태: {status}")
            url_in_result = poll_json.get('result', {}).get('url') if poll_json.get('result') else None
            url_top_level = poll_json.get('url')
            if (status in ['completed', 'succeeded']) and (url_in_result or url_top_level):
                video_url = url_in_result or url_top_level
                break
            elif status == 'failed':
                print("[오류] Creatomate 렌더링 실패:", poll_json)
                sys.exit(1)
            time.sleep(2)
        if not video_url:
            print("[오류] Creatomate 렌더링이 제한 시간 내에 완료되지 않았습니다.")
            sys.exit(1)
        # 동영상 다운로드
        output_dir = os.path.join(os.path.dirname(__file__), 'output')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'creatomate_result.mp4')
        video_resp = requests.get(video_url)
        with open(output_path, "wb") as f:
            f.write(video_resp.content)
        print(f"[완료] 동영상이 {output_path} 에 저장되었습니다.")
    except Exception as e:
        print(f"[오류] 동영상 저장 중 예외 발생: {e}") 