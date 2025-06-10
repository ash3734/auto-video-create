import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def extract_blog_content(url):
    """
    네이버 블로그 글에서 본문 텍스트, 이미지 URL 리스트, 비디오 URL 리스트를 추출
    :param url: 네이버 블로그 글 URL
    :return: (본문 텍스트, 이미지 URL 리스트, 비디오 URL 리스트)
    """
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    # 1. iframe이 있으면 src 추출해서 다시 요청
    iframe = soup.find('iframe', {'id': 'mainFrame'})
    if iframe:
        iframe_url = urljoin(url, iframe['src'])
        resp = requests.get(iframe_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

    # 2. 본문 영역 찾기 (여러 케이스 대응)
    main_area = (
        soup.find('div', {'class': 'se-main-container'}) or
        soup.find('div', {'id': 'postViewArea'}) or
        soup.find('div', {'id': 'postListBody'})
    )
    if not main_area:
        raise ValueError('본문 영역을 찾을 수 없습니다.')

    # 텍스트 추출
    text = main_area.get_text(separator='\n', strip=True)

    # https://postfiles.pstatic.net/MjAyNTA1MDlfMTYg/MDAxNzQ2NzkyNjgyNTc2.ier0FJ-ccb5aPRgLALg5MdbadK33W8m6cgh0jeoMIJQg.wZof1W8HIwiECHl_uHAURh0PmzUBzq3rrP7vOHLRdwQg.JPEG/IMG_2224.JPG?type=w966
    # https://postfiles.pstatic.net/MjAyNTA1MDlfMTYg/MDAxNzQ2NzkyNjgyNTc2.ier0FJ-ccb5aPRgLALg5MdbadK33W8m6cgh0jeoMIJQg.wZof1W8HIwiECHl_uHAURh0PmzUBzq3rrP7vOHLRdwQg.JPEG/IMG_2224.JPG?type=w80_blur

    # 이미지 링크 추출
    images = []
    for img in main_area.find_all('img'):
        src = img.get('src')
        if src:
            full_url = urljoin(url, src)
            if '?type=' in full_url:
                full_url = full_url.split('?type=')[0] + '?type=w966'
            # 도메인 필터링: postfiles.pstatic.net만 허용
            if 'postfiles.pstatic.net' in full_url:
                images.append(full_url)

    # 비디오 링크 추출
    videos = []
    for video in main_area.find_all('video'):
        src = video.get('src')
        if src:
            videos.append(urljoin(url, src))
        # <source src="..."> 구조도 지원
        for source in video.find_all('source'):
            src = source.get('src')
            if src:
                videos.append(urljoin(url, src))

    return text, images, videos

# 콘솔에서만 사용할 선택 함수 (API에서는 사용하지 않음)
def select_videos_by_url(video_urls):
    print("영상 목록:")
    for idx, url in enumerate(video_urls, 1):
        print(f"{idx}. {url}")
    selected_indices = input("원하는 영상 번호를 입력하세요(쉼표로 구분): ")
    try:
        indices = [int(idx.strip()) for idx in selected_indices.split(",")]
        valid_selected_urls = [video_urls[idx-1] for idx in indices if 1 <= idx <= len(video_urls)]
    except Exception:
        print("입력이 올바르지 않습니다. 다시 시도하세요.")
        return []
    if not valid_selected_urls:
        print("입력한 번호가 목록에 없습니다. 다시 시도하세요.")
        return []
    return valid_selected_urls 