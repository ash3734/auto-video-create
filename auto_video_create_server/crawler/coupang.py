from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from typing import List, Dict
import time
from auto_video_create_server.crawler.coupang_cookies import parse_cookies_from_text
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

COUPANG_TODAY_SPECIAL_URL = "https://pages.coupang.com/p/121237?sourceType=oms_goldbox"
CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"

def fetch_today_special_items() -> List[Dict]:
    """
    쿠팡 오늘특가 페이지에서 특가 상품 리스트를 크롤링합니다. (selenium 기반, 쿠키 활용)
    Returns: 상품 정보 dict 리스트 (상품명, 상세링크, 이미지 등)
    """
    print("[크롤러] Selenium 브라우저 실행 시작")
    options = Options()
    # options.add_argument('--headless')  # headless 제거: 실제 브라우저 창이 뜸
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    try:
        print("[크롤러] 페이지 접속: ", COUPANG_TODAY_SPECIAL_URL)
        driver.get(COUPANG_TODAY_SPECIAL_URL)
        # 현재 도메인에 맞는 쿠키를 가져와서 주입
        domain = urlparse(driver.current_url).hostname
        cookies = parse_cookies_from_text(domain)
        for cookie in cookies:
            cookie = cookie.copy()
            cookie.pop('domain', None)
            driver.add_cookie(cookie)
        print("[크롤러] 쿠키 주입 완료, 페이지 새로고침")
        driver.refresh()
        time.sleep(3)
        html = driver.page_source
        print(f"[크롤러] HTML 길이: {len(html)}")
        print(f"[크롤러] HTML 일부: {html[:500]}")
        print("[크롤러] BeautifulSoup 파싱 시작")
        soup = BeautifulSoup(html, "html.parser")
        print("[크롤러] 상품 리스트 추출 시작")
        items = []
        products = soup.select(".discount-product-unit.grid-2")
        print(f"[크롤러] 상품 노드 개수: {len(products)}")
        for idx, product in enumerate(products):
            print(f"[크롤러] 상품 {idx+1} 파싱 중...")
            title_tag = product.select_one(".info_section__title")
            title = title_tag.get_text(strip=True) if title_tag else None
            a_tag = product.find_parent("a")
            link = a_tag["href"] if a_tag and a_tag.has_attr("href") else None
            img_tag = product.select_one(".discount-product-unit__product_image img")
            img = img_tag["src"] if img_tag and img_tag.has_attr("src") else None
            if img and img.startswith("//"): img = "https:" + img
            print(f"  title: {title}")
            print(f"  link: {link}")
            print(f"  img: {img}")
            if title and link and img:
                items.append({
                    "title": title,
                    "link": link,
                    "img": img,
                })
        print(f"[크롤러] 최종 추출 상품 개수: {len(items)}")
        return items
    finally:
        driver.quit()

def fetch_coupang_product_detail(url: str, cookie_text: str):
    print(f"[상세페이지 테스트] Selenium 브라우저 실행 시작: {url}")
    options = Options()
    # options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(url)
        # 쿠키 텍스트를 파싱해서 주입
        cookies = parse_cookies_from_text(cookie_text)
        for cookie in cookies:
            cookie = cookie.copy()
            cookie.pop('domain', None)
            driver.add_cookie(cookie)
        print("[상세페이지 테스트] 쿠키 주입 완료, 페이지 새로고침")
        driver.refresh()
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1.product-title > span.twc-font-bold"))
            )
        except Exception as e:
            print("[상세페이지 테스트] 상품명 대기 실패:", e)
        html = driver.page_source
        print(f"[상세페이지 테스트] HTML 길이: {len(html)}")
        print(f"[상세페이지 테스트] HTML 일부: {html[:500]}")
        # 상세페이지에서 상품명, 가격 등 주요 정보 추출 시도
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.select_one('h1.product-title > span.twc-font-bold')
        title = title_tag.get_text(strip=True) if title_tag else None
        print(f"[상세페이지 테스트] 상품명: {title}")
    finally:
        driver.quit()

if __name__ == "__main__":
    # 상세페이지 테스트용 URL
    test_url = "https://www.coupang.com/vp/products/84025689?vendorItemId=3646048301"
    cookie_text = input("크롬에서 복사한 쿠키를 붙여넣으세요:\n")
    fetch_coupang_product_detail(test_url, cookie_text)
    # 기존 상품 리스트 크롤링은 주석처리
    # items = fetch_today_special_items()
    # for i, item in enumerate(items, 1):
    #     print(f"[{i}] {item['title']}")
    #     print(f"  링크: {item['link']}")
    #     print(f"  이미지: {item['img']}") 