"""
틀린그림 찾기 영상 생성 파이프라인 템플릿
"""
import os
import random
import requests
from .generate_pairs import generate_difference_image
# from .tts import tts_for_difference
# from .utils import ...

CREATOMATE_API_KEY = os.environ.get("CREATOMATE_API_KEY")
CREATOMATE_TEMPLATE_ID = "94e09efb-2899-42c7-bd4c-0600b6a030e3"

DIFFICULTY_MAP = {1: "하", 2: "중", 3: "상"}


def make_find_difference_video(prompt, output_path="find_difference_result.mp4"):
    """
    prompt: 생성할 이미지 주제(예: '카페 내부')
    output_path: 결과 영상 파일 경로
    """
    # 1. 난이도 랜덤 선택
    diff_level = random.choice([1, 2, 3])
    diff_label = DIFFICULTY_MAP[diff_level]
    diff_count = {1: 3, 2: 5, 3: 7}[diff_level]
    print(f"[오늘의 난이도] {diff_label} (level={diff_level})")
    print(f"[틀린그림 개수] {diff_count}개")

    # 2. AI로 틀린그림 한 장짜리 이미지 생성
    img_url = generate_difference_image(prompt, diff_level=diff_level)

    # 3. Creatomate API로 영상 생성 (image1만 사용)
    variables = {
        "image1.source": img_url,
        "difficulty.text": diff_label,
        # 필요시 추가 변수
    }
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
        json=payload
    )
    if response.status_code in (200, 201, 202):
        result = response.json()[0] if isinstance(response.json(), list) else response.json()
        render_id = result["id"]
        video_url = result["url"]
        print("영상 렌더링 시작! 상태:", result["status"])
        # 렌더링 완료까지 폴링
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
                import time; time.sleep(3)
    else:
        print("Creatomate API 오류:", response.status_code, response.text)
    return output_path 