import random
from auto_video_create_server.crawler.naver import extract_blog_content
from auto_video_create_server.scripts.summarize import summarize_for_shorts_sets
from auto_video_create_server.scripts.tts_fal import tts_with_fal_multi, select_images_by_url
from auto_video_create_server.scripts.create_creatomate_video import create_creatomate_video
from mutagen.mp3 import MP3
from transformers import AutoProcessor, AutoModel
from PIL import Image
import torch
from io import BytesIO
import requests
import re

if __name__ == "__main__":
    ##https://blog.naver.com/muk_soul/223786176500
    url = input("네이버 블로그 주소를 입력하세요: ")
    try:
        text, images, video5 = extract_blog_content(url)
        ##print("\n[본문 텍스트]\n", text)
        ##print("\n[이미지 링크]")
        ##for img_url in images:
            ##print(img_url)
        
        # 자동으로 title, first_script 생성
        # 역/동/상호명 추출 (간단히 정규식 활용, 더 정교하게 하려면 별도 함수로 분리 가능)
        # 상호명: 블로그 제목의 마지막 단어 또는 본문에서 '상호명' 패턴 추출(간단화)
        # 역/동: 본문에서 '무슨무슨역', '무슨무슨동' 패턴 추출
        blog_title = text.split('\n')[0] if '\n' in text else text[:30]
        # 역/동 추출
        match_station = re.search(r"([가-힣]+역)", text)
        match_dong = re.search(r"([가-힣]+동)", text)
        location = match_station.group(1) if match_station else (match_dong.group(1) if match_dong else "")
        # 상호명 추출(제목 마지막 단어)
        shop = blog_title.split()[-1] if blog_title.split() else "가게"
        # title, first_script 자동 생성
        if location:
            title = f"{location} {shop}"
            first_script = f"{location} 맛집 {shop} 방문후기 입니다."
        else:
            title = f"{shop}"
            first_script = f"{shop} 방문후기 입니다."
        # summarize_for_shorts_sets 호출 결과: title, first_script, scripts(4개)
        title, first_script, scripts = summarize_for_shorts_sets(text, "", "")
        # scripts: 4개 → 5개로 변환
        scripts = [{"script": first_script}] + scripts
        # 스크립트 개수 체크 및 보정
        if len(scripts) != 5:
            print(f"[경고] 쇼츠 스크립트가 5개가 아닙니다. 반환된 개수: {len(scripts)}")
            while len(scripts) < 5:
                scripts.append({"script": ""})
            if len(scripts) > 5:
                scripts = scripts[:5]
        print("\n[생성된 제목]\n", title)
        print("\n[생성된 첫 스크립트]\n", first_script)
        print("\n[쇼츠용 5세트 스크립트]\n", scripts)

        # 이미지 선택 (스크립트 생성 후)
        filtered_images = [img for img in images if img.startswith("https://postfiles.pstatic.net")]

        # KoCLIP을 이용한 이미지-스크립트 자동 매칭
        # 1. 이미지 다운로드 및 PIL 변환 (전체 images 사용)
        pil_images = []
        for url in filtered_images:
            try:
                response = requests.get(url)
                img = Image.open(BytesIO(response.content)).convert("RGB")
                pil_images.append(img)
            except Exception as e:
                print(f"이미지 다운로드 실패: {url}, {e}")
                pil_images.append(None)

        # 2. 스크립트에서 메뉴명 추출 (2~4번만)
        menu_names = []
        for s in scripts[1:4]:
            try:
                menu = s["script"].split(":")[0].strip()
                menu_names.append(menu)
            except Exception:
                menu_names.append("")

        # 3. KoCLIP 임베딩 및 매칭 (이미지 3개만)
        processor = AutoProcessor.from_pretrained("koclip/koclip-base-pt")
        model = AutoModel.from_pretrained("koclip/koclip-base-pt")
        valid_pil_images = [img for img in pil_images if img is not None]
        image_inputs = processor(images=valid_pil_images, return_tensors="pt")
        with torch.no_grad():
            image_features = model.get_image_features(pixel_values=image_inputs["pixel_values"])
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        text_inputs = processor(text=menu_names, return_tensors="pt", padding=True)
        with torch.no_grad():
            text_features = model.get_text_features(
                input_ids=text_inputs["input_ids"],
                attention_mask=text_inputs["attention_mask"]
            )
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        similarity = text_features @ image_features.T
        best_matches = similarity.argmax(dim=1).cpu().numpy()
        valid_urls = [url for url, img in zip(filtered_images, pil_images) if img is not None]
        matched_images = [valid_urls[idx] for idx in best_matches]
        print("\n[KoCLIP 자동 매칭 이미지]")
        for i, (menu, img_url) in enumerate(zip(menu_names, matched_images)):
            print(f"스크립트 {i+2} ({menu}) → 이미지: {img_url}")
        # image_urls: 첫번째는 사용자가 직접, 2~4번째는 자동매칭, 마지막은 video5
        image_urls = [matched_images[0], matched_images[1], matched_images[2], video5]

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
