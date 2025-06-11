import os
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()

CREATOMATE_API_KEY = os.environ["CREATOMATE_API_KEY"]
CREATOMATE_TEMPLATE_ID = "e78f211a-9e4c-4f5c-a871-36b9d680ee11"

## 네이버 "e78f211a-9e4c-4f5c-a871-36b9d680ee11"
## 유튜브 "14457245-7822-48a6-a711-62d15b739b85"

def create_creatomate_video(image_urls, audio_paths, scripts, title=None, output_path="creatomate_result.mp4", video5=None, **kwargs):
    variables = {
        "image1.source": image_urls[0],
        "image2.source": image_urls[1],
        "image3.source": image_urls[2],
        "image4.source": image_urls[3],
        "audio1.source": audio_paths[0],
        "audio2.source": audio_paths[1],
        "audio3.source": audio_paths[2],
        "audio4.source": audio_paths[3],
        "audio5.source": audio_paths[4],
        "text1.text": scripts[0],
        "text2.text": scripts[1],
        "text3.text": scripts[2],
        "text4.text": scripts[3],
        "text5.text": scripts[4],
    }
    if video5:
        variables["video5.source"] = video5
    if title:
        variables["title.text"] = title
    variables.update(kwargs)
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
        data=json.dumps(payload)
    )
    return response.json()

def get_creatomate_vars(durations):
    creatomate_vars = {}
    for i in range(5):
        creatomate_vars[f"composition_{i+1}.duration"] = durations[i] if i < len(durations) and durations[i] is not None else 0
    times = [0]
    for i in range(1, 5):
        prev_time = times[-1] + (durations[i-1] if i-1 < len(durations) and durations[i-1] is not None else 0)
        times.append(prev_time)
    for i in range(5):
        creatomate_vars[f"composition_{i+1}.time"] = times[i]
    comp5_time = creatomate_vars["composition_5.time"]
    comp5_duration = creatomate_vars["composition_5.duration"]
    total_duration = comp5_time + comp5_duration
    creatomate_vars["composition_title.time"] = 0
    creatomate_vars["composition_title.duration"] = total_duration
    creatomate_vars["composition_logo.time"] = 0
    creatomate_vars["composition_logo.duration"] = total_duration
    creatomate_vars["duration"] = total_duration
    return creatomate_vars
