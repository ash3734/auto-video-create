import os
import requests
import boto3

def upload_to_s3(local_path, bucket, s3_key):
    s3 = boto3.client('s3')
    s3.upload_file(local_path, bucket, s3_key)
    url = f"https://{bucket}.s3.amazonaws.com/{s3_key}"
    return url

def tts_with_supertone(text, output_path, api_key, voice_id, speed=1.2):
    url = f"https://supertoneapi.com/v1/text-to-speech/{voice_id}?output_format=mp3"
    headers = {
        "x-sup-api-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "language": "ko",
        "style": "neutral",
        "model": "sona_speech_1",
        "voice_settings": {
            "pitch_shift": 0,
            "pitch_variance": 1,
            "speed": speed
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    # 응답은 바이너리(mp3) 데이터
    with open(output_path, "wb") as f:
        f.write(response.content)
    # Supertone은 별도의 웹 URL을 제공하지 않으므로, 로컬 경로만 반환
    return output_path, None

def tts_with_supertone_multi(scripts, api_key, voice_id, speed=1.2, output_dir="/tmp/tts_outputs"):
    print("tts_with_supertone_multi 호출")
    os.makedirs(output_dir, exist_ok=True)
    audio_local_paths = []
    audio_urls = []
    bucket = "auto-video-tts-files"
    for idx, item in enumerate(scripts, 1):
        text = item["script"] if isinstance(item, dict) else item
        output_path = os.path.join(output_dir, f"shorts_script_{idx}.mp3")
        local_path, _ = tts_with_supertone(text, output_path, api_key, voice_id, speed)
        audio_local_paths.append(local_path)
        s3_key = f"shorts_script_{idx}.mp3"
        url = upload_to_s3(local_path, bucket, s3_key)
        audio_urls.append(url)
    return audio_local_paths, audio_urls 