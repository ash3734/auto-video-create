import random
from auto_video_create_server.crawler.naver import extract_blog_content
from auto_video_create_server.scripts.summarize import summarize_for_shorts_sets
from auto_video_create_server.scripts.tts_fal import tts_with_fal_multi, select_images_by_url
from auto_video_create_server.scripts.create_creatomate_video import create_creatomate_video
from mutagen.mp3 import MP3

if __name__ == "__main__":
    ##https://blog.naver.com/muk_soul/223786176500
    url = input("네이버 블로그 주소를 입력하세요: ")
    try:
        text, images, video5 = extract_blog_content(url)
        ##print("\n[본문 텍스트]\n", text)
        ##print("\n[이미지 링크]")
        ##for img_url in images:
            ##print(img_url)
        
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
        audio_local_paths, audio_urls = tts_with_fal_multi(
            scripts,
            voice="TRO4gatqxbbwLXHLDLSk",
            stability=0.5,
            similarity_boost=0.5,
            speed=1.15,
            style=0.5
        )
        print("\n[생성된 음성 파일 경로]\n", audio_local_paths)
        print("\n[생성된 음성 파일 URL]\n", audio_urls)

        # 각 음성 파일의 길이(초) 추출 (로컬 경로 기준)
        durations = []
        for path in audio_local_paths:
            try:
                audio = MP3(path)
                durations.append(audio.info.length)
            except Exception as e:
                print(f"{path} 길이 추출 실패: {e}")
                durations.append(None)
        print("\n[음성 파일별 길이(초)]\n", durations)

        # duration_1~5, time_1~5 변수 계산 (composition_1.duration 등으로 변경)
        creatomate_vars = {}
        for i in range(5):
            creatomate_vars[f"composition_{i+1}.duration"] = durations[i] if i < len(durations) and durations[i] is not None else 0
        times = [0]
        for i in range(1, 5):
            prev_time = times[-1] + (durations[i-1] if i-1 < len(durations) and durations[i-1] is not None else 0)
            times.append(prev_time)
        for i in range(5):
            creatomate_vars[f"composition_{i+1}.time"] = times[i]
        print("\n[Creatomate에 넘길 duration, time 변수]\n", creatomate_vars)

        # composition_title, composition_logo의 time/duration 추가
        comp5_time = creatomate_vars["composition_5.time"]
        comp5_duration = creatomate_vars["composition_5.duration"]
        total_duration = comp5_time + comp5_duration
        creatomate_vars["composition_title.time"] = 0
        creatomate_vars["composition_title.duration"] = total_duration
        creatomate_vars["composition_logo.time"] = 0
        creatomate_vars["composition_logo.duration"] = total_duration
        creatomate_vars["duration"] = total_duration

        # Creatomate 영상 생성 (제목 포함)
        create_creatomate_video(
            image_urls, audio_urls, [s["script"] for s in scripts], title=title, video5=video5, **creatomate_vars
        )
    except Exception as e:
        print(f"오류 발생: {e}") 
