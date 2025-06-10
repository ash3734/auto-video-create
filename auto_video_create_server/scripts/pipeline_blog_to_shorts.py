import sys
from crawler.naver import extract_blog_content, select_videos_by_url
from services.summarize import summarize_for_shorts_sets
from services.tts_fal import tts_with_fal_multi, select_images_by_url
from services.create_creatomate_video import create_creatomate_video

if __name__ == "__main__":
    url = input("네이버 블로그 주소를 입력하세요: ")
    text, images, videos = extract_blog_content(url)
    print(f"\n[이미지 {len(images)}개]")
    for i, img in enumerate(images, 1):
        print(f"{i}: {img}")
    print(f"\n[영상 {len(videos)}개]")
    for i, vid in enumerate(videos, 1):
        print(f"{i}: {vid}")

    title, scripts = summarize_for_shorts_sets(text)
    print(f"\n[쇼츠 제목] {title}")
    print("[쇼츠 스크립트]")
    for i, s in enumerate(scripts, 1):
        print(f"{i}: {s['script'] if isinstance(s, dict) else s}")

    # 이미지 선택
    selected_images = select_images_by_url(images)
    if len(selected_images) < 4:
        print("이미지는 4개 이상 선택해야 합니다.")
        sys.exit(1)
    selected_images = selected_images[:4]

    # 영상 선택 (선택적)
    selected_video = None
    if videos:
        selected_videos = select_videos_by_url(videos)
        if selected_videos:
            selected_video = selected_videos[0]

    # TTS 변환
    print("\n[TTS 변환 진행 중...]")
    audio_local_paths, audio_urls = tts_with_fal_multi(scripts)
    if len(audio_local_paths) < 5:
        print("TTS 음성 파일이 5개 미만입니다. 스크립트 또는 TTS 오류를 확인하세요.")
        sys.exit(1)
    audio_local_paths = audio_local_paths[:5]

    # 동영상 생성
    print("\n[동영상 생성 진행 중...]")
    result = create_creatomate_video(
        image_urls=selected_images,
        audio_paths=audio_local_paths,
        scripts=[s['script'] if isinstance(s, dict) else s for s in scripts],
        title=title,
        video5=selected_video
    )
    print("\n[Creatomate API 응답]")
    print(result)
    print("\n파이프라인 완료!") 