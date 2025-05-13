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

def tts_with_fal(text, output_path=None, voice="Bill"):
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
            "voice": voice
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

def tts_with_fal_multi(scripts, voice="Rachel"):
    audio_urls = []
    for idx, item in enumerate(scripts, 1):
        text = item["script"]
        output_path = get_next_seq_filename(idx)
        url = tts_with_fal(text, output_path=output_path, voice=voice)
        audio_urls.append(url)
    return audio_urls 
