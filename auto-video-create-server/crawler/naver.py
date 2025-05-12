import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def extract_blog_content(url):
    """
    네이버 블로그 글에서 본문 텍스트와 이미지 링크(이미지 URL)만 추출
    :param url: 네이버 블로그 글 URL
    :return: (본문 텍스트, 이미지 URL 리스트)
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

    # 이미지 링크 추출
    images = []
    for img in main_area.find_all('img'):
        src = img.get('src')
        if src:
            # 절대경로로 변환
            images.append(urljoin(url, src))

    return text, images 
