from fastapi import FastAPI, Response, Query
from pydantic import BaseModel
from auto_video_create_server.crawler.naver import extract_blog_content
from auto_video_create_server.scripts.summarize import summarize_for_shorts_sets
import requests
import time
from typing import List, Optional

# TTS, Creatomate 관련 함수 임포트 필요 (예시)
# from auto_video_create_server.services.tts_supertone import tts_supertone_multi
# from auto_video_create_server.services.create_creatomate_video import create_creatomate_video_and_get_url

app = FastAPI()

class ExtractMediaRequest(BaseModel):
    blog_url: str

class ExtractMediaResponse(BaseModel):
    status: str
    scripts: list[str]
    images: list[str]
    videos: list[str]
    title: str = None
    message: str = None

class GenerateVideoRequest(BaseModel):
    title: str
    scripts: List[str]
    images: List[str]  # 4개
    video: Optional[str] = None  # 마지막 스크립트에 매핑된 영상

class GenerateVideoResponse(BaseModel):
    status: str
    video_url: Optional[str] = None
    message: Optional[str] = None

@app.post("/api/extract-media", response_model=ExtractMediaResponse)
def extract_media(req: ExtractMediaRequest):
    try:
        text, images, videos = extract_blog_content(req.blog_url)
        title, scripts = summarize_for_shorts_sets(text)
        # scripts가 dict이든 str이든 robust하게 문자열만 추출
        script_texts = []
        for item in scripts[:5]:
            if isinstance(item, dict):
                script_texts.append(item.get("script", ""))
            elif isinstance(item, str):
                script_texts.append(item)
            else:
                script_texts.append("")
        return {
            "status": "success",
            "scripts": script_texts,
            "images": images,
            "videos": videos,
            "title": title
        }
    except Exception as e:
        return {
            "status": "error",
            "scripts": [],
            "images": [],
            "videos": [],
            "title": None,
            "message": str(e)
        }

@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}

@app.get("/api/image-proxy")
def image_proxy(url: str = Query(..., description="이미지 원본 URL")):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg")
        return Response(content=r.content, media_type=content_type)
    except Exception as e:
        return Response(content=b"", status_code=404)

@app.post("/api/generate-video", response_model=GenerateVideoResponse)
def generate_video(req: GenerateVideoRequest):
    try:
        # 1. TTS 변환 (scripts → mp3 url)
        # audio_urls = tts_supertone_multi(req.scripts)  # 5개 mp3 url 반환
        # (여기서는 예시로 빈 리스트)
        audio_urls = [f"https://dummy-tts/{i}.mp3" for i in range(5)]
        durations = [3.5, 4.0, 3.8, 4.2, 5.0]  # 예시: 각 mp3 길이(초)

        # 2. Creatomate 영상 생성 (이미지 4개, 영상 1개, 오디오 5개, 스크립트, title)
        # video_url = create_creatomate_video_and_get_url(
        #     images=req.images,
        #     audio_urls=audio_urls,
        #     scripts=req.scripts,
        #     title=req.title,
        #     video5=req.video,
        #     durations=durations
        # )
        # (여기서는 예시로 더미 url)
        video_url = "https://creatomate.com/rendered/final_video.mp4"

        return {"status": "success", "video_url": video_url}
    except Exception as e:
        return {"status": "error", "message": str(e)} 