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
import openai
import base64
import json
import time

if __name__ == "__main__":
    url = input("네이버 블로그 주소를 입력하세요: ")
    try:
        text, images, video5 = extract_blog_content(url)

        filtered_images = [img for img in images if img.startswith("https://postfiles.pstatic.net")]

        print("[이미지 목록]")
        for i, url in enumerate(filtered_images, 1):
            print(f"{i}: {url}")

        ##print(f"[DEBUG] filtered_images({len(filtered_images)}): {filtered_images}")

        title, scripts = summarize_for_shorts_sets(text)
        print("[DEBUG] scripts({}): {}".format(len(scripts), json.dumps(scripts, ensure_ascii=False)))
        # 이미지 해석 및 Vision API 관련 코드는 삭제됨

        # 음성 변환용 스크립트 리스트 (5개)
        script_texts = [item.get("script", "") for item in scripts]
        while len(script_texts) < 5:
            script_texts.append("")
        audio_local_paths, audio_urls = tts_with_fal_multi(
            [{"script": s} for s in script_texts],
            voice="TRO4gatqxbbwLXHLDLSk",
            stability=0.5,
            similarity_boost=0.5,
            speed=1.15,
            style=0.5
        )
        print(f"[DEBUG] audio_urls({len(audio_urls)}): {audio_urls}")
        print(f"[DEBUG] script_texts({len(script_texts)}): {script_texts}")
        # 항상 5개로 맞추기
        while len(audio_urls) < 5:
            audio_urls.append(audio_urls[0])
        while len(script_texts) < 5:
            script_texts.append("")

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
            image_b64_list, audio_urls, script_texts, title=title, video5=video5, **creatomate_vars
        )

    except Exception as e:
        print(f"오류 발생: {e}") 