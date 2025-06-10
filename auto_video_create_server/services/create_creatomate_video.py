import os
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()

CREATOMATE_API_KEY = os.environ["CREATOMATE_API_KEY"]
CREATOMATE_TEMPLATE_ID = "14457245-7822-48a6-a711-62d15b739b85"

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
