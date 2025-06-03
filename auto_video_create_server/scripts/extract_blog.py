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

# 한글 텍스트를 영어로 번역하는 함수 (OpenAI API 활용)
def translate_to_english(text):
    prompt = f"Translate the following Korean menu name or sentence to natural English. Only return the translation, no explanation.\n\n{text}"
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50
    )
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    url = input("네이버 블로그 주소를 입력하세요: ")
    try:
        text, images, video5 = extract_blog_content(url)

        filtered_images = [img for img in images if img.startswith("https://postfiles.pstatic.net")]
        image_b64_list = []
        for url in filtered_images:
            try:
                img_data = requests.get(url).content
                img_b64 = base64.b64encode(img_data).decode('utf-8')
                image_b64_list.append(f"data:image/jpeg;base64,{img_b64}")
            except Exception as e:
                print(f"이미지 다운로드/인코딩 실패: {url}, {e}")
                image_b64_list.append(None)
        # None이 아닌 것만 사용
        valid_images = [(b64, url) for b64, url in zip(image_b64_list, filtered_images) if b64 is not None]
        if not valid_images:
            raise RuntimeError("사용 가능한 이미지가 없습니다.")
        image_b64_list, filtered_images = zip(*valid_images)

        print("[이미지 목록]")
        for i, url in enumerate(filtered_images, 1):
            print(f"{i}: {url}")

        print(f"[DEBUG] filtered_images({len(filtered_images)}): {filtered_images}")

        # 1단계: 스크립트만 먼저 생성
        title, scripts = summarize_for_shorts_sets(text)
        print("[DEBUG] scripts({}): {}".format(len(scripts), json.dumps(scripts, ensure_ascii=False)))

        # 2단계: 각 이미지에 대해 Vision API로 영어 설명 생성
        image_descriptions = []
        for idx, b64 in enumerate(image_b64_list):
            prompt = (
                "What is the main food or dish in this image? "
                "If you see any meat, describe the type (e.g., pork, beef, chicken) and its appearance (e.g., raw, grilled, marbled, sliced, etc.) in one English sentence. "
                "If there is no food, describe the main subject."
            )
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": b64}}
                    ]
                }
            ]
            response = openai.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                max_tokens=100
            )
            answer = response.choices[0].message.content.strip()
            image_descriptions.append(answer)
            print(f"[Image {idx+1} English Description] {answer}")
            time.sleep(0.3)  # rate limit 방지용 딜레이

        # 3단계: 각 스크립트별로 영어 번역 후 이미지 설명(영어)와 매칭
        image_urls = []
        for i, item in enumerate(scripts[:4]):
            script_text_ko = item["script"]
            script_text_en = translate_to_english(script_text_ko)
            desc_list = "\n".join([f"{idx+1}. {desc}" for idx, desc in enumerate(image_descriptions)])
            prompt = (
                "Which image description best matches the main dish or food described below? "
                "Focus on the type of meat, its appearance, and the overall food presentation. "
                "Answer only with the number.\n"
                f"Script: {script_text_en}\n"
                f"Image descriptions:\n" + desc_list
            )
            print(f"\n[Text Model Matching Prompt - Script {i+1} (EN)]\n{prompt}")
            messages = [
                {"role": "user", "content": prompt}
            ]
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=10
            )
            answer = response.choices[0].message.content.strip()
            print(f"[Text Model Matching Response - Script {i+1} (EN)]\n{answer}")
            import re
            match = re.search(r"(\d+)", answer)
            idx = int(match.group(1)) if match and 1 <= int(match.group(1)) <= len(filtered_images) else 1
            image_urls.append(filtered_images[idx-1])
        while len(image_urls) < 4:
            image_urls.append(filtered_images[0])
        image_urls = [filtered_images[0]] + image_urls[:3]
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
        print(f"[DEBUG] image_urls({len(image_urls)}): {image_urls}")
        print(f"[DEBUG] audio_urls({len(audio_urls)}): {audio_urls}")
        print(f"[DEBUG] script_texts({len(script_texts)}): {script_texts}")
        # 항상 5개로 맞추기
        while len(image_urls) < 5:
            image_urls.append(image_urls[0])
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
            image_urls, audio_urls, script_texts, title=title, video5=video5, **creatomate_vars
        )

    except Exception as e:
        print(f"오류 발생: {e}") 