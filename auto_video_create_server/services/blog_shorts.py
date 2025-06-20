from crawler.naver import extract_blog_content
from .summarize import summarize_for_shorts_sets

# 필요시 아래 함수들도 services. 경로로 import
# from .tts_fal import ...
# from .create_creatomate_video import ...
# from .extract_blog import ...

def get_blog_media_and_scripts(blog_url: str):
    text, images, videos = extract_blog_content(blog_url)
    title, scripts = summarize_for_shorts_sets(text)
    return {"text": text, "images": images, "videos": videos, "title": title, "scripts": scripts} 