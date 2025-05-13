import random
from auto_video_create_server.crawler.naver import extract_blog_content
from auto_video_create_server.scripts.summarize import summarize_for_shorts_sets
from auto_video_create_server.scripts.tts_fal import tts_with_fal_multi
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
        
        # postfiles.pstatic.net 도메인만 필터링 후 랜덤 5장 추출, 정렬
        filtered_images = [img for img in images if img.startswith("https://postfiles.pstatic.net")]
        selected_images = sorted(random.sample(filtered_images, min(5, len(filtered_images))))
        image_urls = selected_images
        print("\n[최종 추출된 이미지 5장]")
        for img_url in image_urls:
            print(img_url)

        # 쇼츠용 5세트 스크립트 생성
        scripts = summarize_for_shorts_sets(text)
        print("\n[쇼츠용 5세트 스크립트]\n", scripts)

        # 쇼츠 스크립트 5개 음성 변환
        audio_paths = tts_with_fal_multi(scripts)
        print("\n[생성된 음성 파일 경로]\n", audio_paths)

        # Creatomate 영상 생성
        create_creatomate_video(image_urls, audio_paths, [s["script"] for s in scripts])
    except Exception as e:
        print(f"오류 발생: {e}") 
