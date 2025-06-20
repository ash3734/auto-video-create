from .blog_shorts import extract_blog_content, summarize_for_shorts_sets

if __name__ == "__main__":
    url = input("네이버 블로그 주소를 입력하세요: ")
    text, images, videos = extract_blog_content(url)
    print("[이미지 목록]")
    for i, img in enumerate(images, 1):
        print(f"{i}: {img}")
    title, scripts = summarize_for_shorts_sets(text)
    print("[스크립트]")
    for s in scripts:
        print(s) 