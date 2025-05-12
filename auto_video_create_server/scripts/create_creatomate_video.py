import os
import requests
import json

CREATOMATE_API_KEY = "5aa1d7962e1744bb87d0f0f4e97167410709f3425e9817eedde66f3e275dcaed6558ea9a1045f24a111f64b8d9a444ed"
TEMPLATE_PATH = "auto_video_create_server/templates/creatomate_image_audio_subtitle_set.json"

def create_creatomate_video(image_urls, audio_paths, scripts, output_path="creatomate_result.mp4"):
    # 1. 템플릿 로드
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = json.load(f)

    # 2. 템플릿 변수 치환 (3세트 기준)
    variables = {
        "image1": image_urls[0],
        "image2": image_urls[1],
        "image3": image_urls[2],
        "audio1": audio_paths[0],
        "audio2": audio_paths[1],
        "audio3": audio_paths[2],
        "subtitle1": scripts[0],
        "subtitle2": scripts[1],
        "subtitle3": scripts[2],
    }
    payload = {
        "template": template,
        "variables": variables
    }

    # 3. Creatomate API 호출
    response = requests.post(
        "https://api.creatomate.com/v1/renders",
        headers={
            "Authorization": f"Bearer {CREATOMATE_API_KEY}",
            "Content-Type": "application/json"
        },
        data=json.dumps(payload)
    )

    if response.status_code == 201:
        result = response.json()
        video_url = result["url"]
        print("영상 생성 완료! 다운로드 중:", video_url)
        # 4. 영상 다운로드
        video_data = requests.get(video_url).content
        with open(output_path, "wb") as f:
            f.write(video_data)
        print("영상 저장 완료:", output_path)
    else:
        print("Creatomate API 오류:", response.status_code, response.text)

# 사용 예시
def example_usage():
    image_urls = [
        "https://example.com/image1.jpg",
        "https://example.com/image2.jpg",
        "https://example.com/image3.jpg"
    ]
    audio_paths = [
        "tts_outputs/shorts_script_1.wav",
        "tts_outputs/shorts_script_2.wav",
        "tts_outputs/shorts_script_3.wav"
    ]
    scripts = [
        "첫 번째 대사",
        "두 번째 대사",
        "세 번째 대사"
    ]
    create_creatomate_video(image_urls, audio_paths, scripts)

if __name__ == "__main__":
    example_usage()
