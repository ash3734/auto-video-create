import os
import fal_client
import requests
from dotenv import load_dotenv

load_dotenv()

FAL_KEY = os.environ["FAL_KEY"]
fal_client.api_key = FAL_KEY

AUDIO_SAVE_DIR = "tts_outputs"

# 폴더가 없으면 생성
os.makedirs(AUDIO_SAVE_DIR, exist_ok=True)

def get_next_seq_filename(seq):
    return os.path.join(AUDIO_SAVE_DIR, f"shorts_script_{seq}.wav")

def tts_with_fal(text, output_path=None, voice="Bill", stability=0.5, similarity_boost=0.5, speed=1, style=0.5):
    def on_queue_update(update):
        if isinstance(update, fal_client.InProgress):
            for log in update.logs:
                print(log["message"])

    if output_path is None:
        output_path = get_next_seq_filename(1)

    result = fal_client.subscribe(
        "fal-ai/elevenlabs/tts/turbo-v2.5",
        arguments={
            "text": text,
            "voice": voice,
            "stability": stability,
            "similarity_boost": similarity_boost,
            "speed": speed,
            "style": style
        },
        with_logs=True,
        on_queue_update=on_queue_update,
    )
    audio = result.get("audio")
    if audio and isinstance(audio, dict) and "url" in audio:
        audio_url = audio["url"]
        # 필요시 로컬 저장
        audio_data = requests.get(audio_url).content
        with open(output_path, "wb") as f:
            f.write(audio_data)
        print("음성 파일 저장 완료:", output_path)
        return audio_url  # url 반환
    else:
        print("TTS 요청 실패:", result)
        return None

def tts_with_fal_multi(
    scripts,
    voice="Rachel",
    stability=0.5,
    similarity_boost=0.5,
    speed=1,
    style=0.5
):
    audio_urls = []
    for idx, item in enumerate(scripts, 1):
        text = item["script"]
        # '메뉴명 : 가격\n설명' 형식이면 가격을 제외
        if ":" in text and "\n" in text:
            menu_and_price, desc = text.split("\n", 1)
            if ":" in menu_and_price:
                menu = menu_and_price.split(":")[0].strip()
                text = f"{menu}\n{desc.strip()}"
        output_path = get_next_seq_filename(idx)
        url = tts_with_fal(
            text,
            output_path=output_path,
            voice=voice,
            stability=stability,
            similarity_boost=similarity_boost,
            speed=speed,
            style=style
        )
        audio_urls.append(url)
    return audio_urls

def select_images_by_url(image_urls):
    print("이미지 목록:")
    for idx, url in enumerate(image_urls, 1):
        print(f"{idx}. {url}")
    selected_urls = input("원하는 이미지 URL을 직접 입력하세요(쉼표로 구분): ")
    selected_urls = [url.strip() for url in selected_urls.split(",")]
    # 입력된 URL이 실제 리스트에 있는지 검증
    valid_selected_urls = [url for url in selected_urls if url in image_urls]
    if not valid_selected_urls:
        print("입력한 URL이 목록에 없습니다. 다시 시도하세요.")
        return []
    return valid_selected_urls 
