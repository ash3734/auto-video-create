import random
from auto_video_create_server.crawler.naver import extract_blog_content
from auto_video_create_server.scripts.summarize import summarize_for_shorts_sets
from auto_video_create_server.scripts.tts_fal import tts_with_fal_multi
from auto_video_create_server.scripts.create_creatomate_video import create_creatomate_video
from mutagen.mp3 import MP3
from transformers import AutoProcessor, AutoModel
from PIL import Image
import torch
from io import BytesIO
import requests

if __name__ == "__main__":
    url = input("네이버 블로그 주소를 입력하세요: ")
    try:
        text, images, video5 = extract_blog_content(url)

        # 쇼츠용 제목, 첫 스크립트, 4개 스크립트 자동 생성
        title, first_script, scripts = summarize_for_shorts_sets(text, "", "")
        scripts = [{"script": first_script}] + scripts
        if len(scripts) != 5:
            print(f"[경고] 쇼츠 스크립트가 5개가 아닙니다. 반환된 개수: {len(scripts)}")
            while len(scripts) < 5:
                scripts.append({"script": ""})
            if len(scripts) > 5:
                scripts = scripts[:5]
        print("\n[생성된 제목]", title)
        print("[생성된 첫 스크립트]", first_script)
        print("[쇼츠용 5세트 스크립트]", scripts)

        filtered_images = [img for img in images if img.startswith("https://postfiles.pstatic.net")]
        print("이미지 목록:")
        for idx, url in enumerate(filtered_images, 1):
            print(f"{idx}. {url}")
        selected_indices = input("사용할 이미지 번호를 4개 입력하세요(쉼표로 구분): ")
        indices = [int(idx.strip()) for idx in selected_indices.split(",") if idx.strip().isdigit() and 1 <= int(idx.strip()) <= len(filtered_images)]
        if len(indices) < 4:
            print("4개 미만 선택됨, 부족한 부분은 첫 번째 이미지로 채웁니다.")
            indices += [1] * (4 - len(indices))
        image_urls = [filtered_images[i-1] for i in indices[:4]]

        # 음성 변환
        audio_local_paths, audio_urls = tts_with_fal_multi(
            scripts,
            voice="TRO4gatqxbbwLXHLDLSk",
            stability=0.5,
            similarity_boost=0.5,
            speed=1.15,
            style=0.5
        )
        print("\n[생성된 음성 파일 경로]", audio_local_paths)
        print("[생성된 음성 파일 URL]", audio_urls)

        # 각 음성 파일의 길이(초) 추출
        durations = []
        for path in audio_local_paths:
            try:
                audio = MP3(path)
                durations.append(audio.info.length)
            except Exception as e:
                print(f"{path} 길이 추출 실패: {e}")
                durations.append(None)
        print("\n[음성 파일별 길이(초)]", durations)

        # Creatomate 변수 계산
        creatomate_vars = {}
        for i in range(5):
            creatomate_vars[f"composition_{i+1}.duration"] = durations[i] if i < len(durations) and durations[i] is not None else 0
        times = [0]
        for i in range(1, 5):
            prev_time = times[-1] + (durations[i-1] if i-1 < len(durations) and durations[i-1] is not None else 0)
            times.append(prev_time)
        for i in range(5):
            creatomate_vars[f"composition_{i+1}.time"] = times[i]
        print("\n[Creatomate에 넘길 duration, time 변수]", creatomate_vars)

        comp5_time = creatomate_vars["composition_5.time"]
        comp5_duration = creatomate_vars["composition_5.duration"]
        total_duration = comp5_time + comp5_duration
        creatomate_vars["composition_title.time"] = 0
        creatomate_vars["composition_title.duration"] = total_duration
        creatomate_vars["composition_logo.time"] = 0
        creatomate_vars["composition_logo.duration"] = total_duration
        creatomate_vars["duration"] = total_duration

        # Creatomate 영상 생성
        create_creatomate_video(
            image_urls, audio_urls, [s["script"] for s in scripts], title=title, video5=video5, **creatomate_vars
        )
    except Exception as e:
        print(f"오류 발생: {e}") 