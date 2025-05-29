import os
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()

CREATOMATE_API_KEY = os.environ["CREATOMATE_API_KEY"]
CREATOMATE_TEMPLATE_ID = "14457245-7822-48a6-a711-62d15b739b85"  # 새 템플릿 ID로 변경

def create_creatomate_video(image_urls, audio_paths, scripts, title=None, output_path="creatomate_result.mp4", video5=None, **kwargs):
    variables = {
        "image1.source": image_urls[0],
        "image2.source": image_urls[1],
        "image3.source": image_urls[2],
        "image4.source": image_urls[3],
        "audio1.source": audio_paths[0],
        "audio2.source": audio_paths[1],
        "audio3.source": audio_paths[2],
        "audio4.source": audio_paths[3],
        "audio5.source": audio_paths[4],
        "text1.text": scripts[0],
        "text2.text": scripts[1],
        "text3.text": scripts[2],
        "text4.text": scripts[3],
        "text5.text": scripts[4],
    }
    if video5:
        variables["video5.source"] = video5
    if title:
        variables["title.text"] = title
    # 추가 변수(duration_1~5, time_1~5 등) 반영
    variables.update(kwargs)
    payload = {
        "template_id": CREATOMATE_TEMPLATE_ID,
        "modifications": variables
    }
    response = requests.post(
        "https://api.creatomate.com/v1/renders",
        headers={
            "Authorization": f"Bearer {CREATOMATE_API_KEY}",
            "Content-Type": "application/json"
        },
        data=json.dumps(payload)
    )

    if response.status_code in (200, 201, 202):
        result = response.json()[0] if isinstance(response.json(), list) else response.json()
        render_id = result["id"]
        video_url = result["url"]
        print("영상 렌더링 시작! 상태:", result["status"])
        # 폴링: status가 succeeded가 될 때까지 대기
        while True:
            poll = requests.get(
                f"https://api.creatomate.com/v1/renders/{render_id}",
                headers={"Authorization": f"Bearer {CREATOMATE_API_KEY}"}
            )
            poll_result = poll.json()
            if poll_result["status"] == "succeeded":
                video_url = poll_result["url"]
                print("영상 렌더링 완료! 다운로드 중:", video_url)
                video_data = requests.get(video_url).content
                with open(output_path, "wb") as f:
                    f.write(video_data)
                print("영상 저장 완료:", output_path)
                break
            elif poll_result["status"] == "failed":
                print("영상 렌더링 실패:", poll_result)
                break
            else:
                print("렌더링 중... (상태:", poll_result["status"], ")")
                time.sleep(3)
    else:
        print("Creatomate API 오류:", response.status_code, response.text)