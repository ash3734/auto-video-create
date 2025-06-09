"""
find_difference 전체 자동화 파이프라인

실행 방법:
$ python3 -m auto_video_create_server.find_difference.daily_pipeline
"""
from auto_video_create_server.find_difference.prompt_generator import get_today_prompt
from auto_video_create_server.find_difference.make_video import make_find_difference_video

if __name__ == "__main__":
    prompt = get_today_prompt()
    print("오늘의 프롬프트:", prompt)
    make_find_difference_video(prompt) 