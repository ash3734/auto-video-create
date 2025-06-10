from crawler.naver import extract_blog_content
from scripts.summarize import summarize_for_shorts_sets

def get_blog_media_and_scripts(blog_url: str):
    text, images, videos = extract_blog_content(blog_url)
    title, scripts = summarize_for_shorts_sets(text)
    return {"text": text, "images": images, "videos": videos, "title": title, "scripts": scripts} 