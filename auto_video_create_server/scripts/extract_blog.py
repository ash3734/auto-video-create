import random
from auto_video_create_server.crawler.naver import extract_blog_content
from auto_video_create_server.scripts.summarize import summarize_for_shorts_sets
from auto_video_create_server.scripts.tts_fal import tts_with_fal_multi, select_images_by_url
from auto_video_create_server.scripts.create_creatomate_video import create_creatomate_video

if __name__ == "__main__":
    ##https://blog.naver.com/muk_soul/223786176500
    url = input("네이버 블로그 주소를 입력하세요: ")
    try:
        text, images = extract_blog_content(url)
        print("\n[본문 텍스트]\n", text)
        print("\n[이미지 링크]")
        for img_url in images:
            print(img_url)
        
        # 쇼츠용 5세트 스크립트 및 제목 생성
        title = input("제목을 입력하세요: ")
        first_script = input("첫 번째 스크립트를 입력하세요: ")
        title, scripts = summarize_for_shorts_sets(text, title, first_script)
        print("\n[생성된 제목]\n", title)
        print("\n[쇼츠용 5세트 스크립트]\n", scripts)

        # 이미지 선택 (스크립트 생성 후)
        filtered_images = [img for img in images if img.startswith("https://postfiles.pstatic.net")]
        image_urls = select_images_by_url(filtered_images)
        print("\n[최종 선택된 이미지]")
        for img_url in image_urls:
            print(img_url)

        # 쇼츠 스크립트 5개 음성 변환
        audio_paths = tts_with_fal_multi(
            scripts,
            voice="ZZ4xhVcc83kZBfNIlIIz",
            stability=0.5,
            similarity_boost=0.5,
            speed=1,
            style=0.5
        )
        print("\n[생성된 음성 파일 경로]\n", audio_paths)

        # Creatomate 영상 생성 (제목 포함)
        create_creatomate_video(image_urls, audio_paths, [s["script"] for s in scripts], title=title)
    except Exception as e:
        print(f"오류 발생: {e}") 
