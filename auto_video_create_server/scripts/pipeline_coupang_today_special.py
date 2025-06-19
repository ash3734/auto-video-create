import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.coupang import fetch_today_special_items

def main():
    print("[쿠팡 오늘특가 추천 파이프라인]")
    items = fetch_today_special_items()
    print(f"오늘의 특가 상품 {len(items)}개:")
    for i, item in enumerate(items, 1):
        print(f"[{i}] {item['title']}")
        print(f"  링크: {item['link']}")
        print(f"  이미지: {item['img']}")
    print("파이프라인 초기화 완료. 상세 로직은 추후 구현 예정.")

if __name__ == "__main__":
    main() 