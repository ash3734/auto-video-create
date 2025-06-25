import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import os
from typing import Tuple, List


def extract_blog_content(url: str) -> Tuple[str, List[str], List[str]]:
    """
    네이버 블로그 글에서 본문 텍스트, 이미지 URL 리스트, 비디오 URL 리스트를 추출 (Selenium 기반)
    :param url: 네이버 블로그 글 URL
    :return: (본문 텍스트, 이미지 URL 리스트, 비디오 URL 리스트)
    """
    is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
    driver = None
    if is_lambda:
        # Lambda 환경: headless_chrome layer 사용
        try:
            from headless_chrome import create_driver
        except ImportError:
            raise RuntimeError("headless_chrome layer가 Lambda에 추가되어 있지 않습니다.")
        driver = create_driver([
            "--window-size=1280,2000",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--headless"
        ])
    else:
        # 로컬/기타 환경: 기존 방식
        chrome_bin = os.environ.get("CHROME_BINARY")
        driver_bin = os.environ.get("CHROMEDRIVER")
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1280,2000')
        if chrome_bin:
            chrome_options.binary_location = chrome_bin
        if driver_bin:
            from selenium.webdriver.chrome.service import Service
            service = Service(driver_bin)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    time.sleep(2)  # 네트워크 상황에 따라 조정

    # 2. iframe(mainFrame) 내부로 진입
    try:
        iframe = driver.find_element(By.ID, 'mainFrame')
        driver.switch_to.frame(iframe)
        time.sleep(1)
    except Exception:
        pass  # iframe이 없으면 그대로 진행

    # 3. 전체 HTML 파싱
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    # 4. 본문 영역 찾기 (여러 케이스 대응)
    main_area = (
        soup.find('div', {'class': 'se-main-container'}) or
        soup.find('div', {'id': 'postViewArea'}) or
        soup.find('div', {'id': 'postListBody'})
    )
    if not main_area:
        main_area = soup  # fallback: 전체 soup에서 찾기

    # 텍스트 추출
    text = main_area.get_text(separator='\n', strip=True)

    # https://postfiles.pstatic.net/MjAyNTA1MDlfMTYg/MDAxNzQ2NzkyNjgyNTc2.ier0FJ-ccb5aPRgLALg5MdbadK33W8m6cgh0jeoMIJQg.wZof1W8HIwiECHl_uHAURh0PmzUBzq3rrP7vOHLRdwQg.JPEG/IMG_2224.JPG?type=w966
    # https://postfiles.pstatic.net/MjAyNTA1MDlfMTYg/MDAxNzQ2NzkyNjgyNTc2.ier0FJ-ccb5aPRgLALg5MdbadK33W8m6cgh0jeoMIJQg.wZof1W8HIwiECHl_uHAURh0PmzUBzq3rrP7vOHLRdwQg.JPEG/IMG_2224.JPG?type=w80_blur

    # 이미지 링크 추출
    images = []
    img_count = 0
    for img in main_area.find_all('img'):
        src = img.get('src')
        if src:
            full_url = urljoin(url, src)
            if '?type=' in full_url:
                full_url = full_url.split('?type=')[0] + '?type=w966'
            # 도메인 필터링: postfiles.pstatic.net만 허용
            if 'postfiles.pstatic.net' in full_url:
                images.append(full_url)
                img_count += 1
                print(f"[이미지 {img_count}] {full_url}")

    # 비디오 링크 추출 (동적으로 렌더링된 video 태그 포함)
    videos = []
    video_count = 0
    # Selenium으로 video 태그의 src가 없을 때 전체 DOM에서 재생 버튼 후보(button) 모두 클릭 시도
    video_elems = driver.find_elements(By.TAG_NAME, "video")
    for video_elem in video_elems:
        src = video_elem.get_attribute("src")
        if not src:
            # src가 없을 때 전체 DOM에서 재생 버튼 후보(button) 모두 클릭 시도
            try:
                # 1. svg.pzp-ui-icon__svg를 포함하는 button
                svg_buttons = driver.find_elements(By.CSS_SELECTOR, "button:has(svg.pzp-ui-icon__svg)")
                # 2. class에 pzp-brand-playback-button 또는 pzp-playback-switch가 포함된 button
                class_buttons = driver.find_elements(By.CSS_SELECTOR, "button.pzp-brand-playback-button, button.pzp-playback-switch")
                # 3. 중복 제거
                all_buttons = list({btn: None for btn in svg_buttons + class_buttons}.keys())
                for btn in all_buttons:
                    driver.execute_script("arguments[0].scrollIntoView();", btn)
                    time.sleep(0.3)
                    try:
                        btn.click()
                        time.sleep(1.2)
                        print("재생 버튼 클릭 성공 (src 없음)")
                        # 클릭 후 바로 src 재확인
                        src = video_elem.get_attribute("src")
                        if src:
                            break
                    except Exception as e:
                        print("재생 버튼 클릭 실패 (src 없음):", e)
            except Exception as e:
                print("재생 버튼 탐색/클릭 중 예외 (src 없음):", e)
        if src and src not in videos:
            full_url = urljoin(url, src)
            videos.append(full_url)
            video_count += 1
            print(f"[비디오 Selenium {video_count}] {full_url}")
    # BeautifulSoup으로도 한 번 더 (기존 코드)
    for video in main_area.find_all('video'):
        src = video.get('src')
        if src:
            full_url = urljoin(url, src)
            if full_url not in videos:
                videos.append(full_url)
                video_count += 1
                print(f"[비디오 {video_count}] {full_url}")
        for source in video.find_all('source'):
            src = source.get('src')
            if src:
                full_url = urljoin(url, src)
                if full_url not in videos:
                    videos.append(full_url)
                    video_count += 1
                    print(f"[비디오 {video_count}] {full_url}")
    # main_area에서 못 찾은 경우 soup 전체에서 한 번 더 찾기 (중복 방지)
    if not videos:
        for video in soup.find_all('video'):
            src = video.get('src')
            if src:
                full_url = urljoin(url, src)
                if full_url not in videos:
                    videos.append(full_url)
                    video_count += 1
                    print(f"[비디오(전체) {video_count}] {full_url}")
            for source in video.find_all('source'):
                src = source.get('src')
                if src:
                    full_url = urljoin(url, src)
                    if full_url not in videos:
                        videos.append(full_url)
                        video_count += 1
                        print(f"[비디오(전체) {video_count}] {full_url}")

    driver.quit()
    return text, images, videos

# 콘솔에서만 사용할 선택 함수 (API에서는 사용하지 않음)
def select_videos_by_url(video_urls):
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